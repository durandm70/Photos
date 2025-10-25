#!/usr/bin/env python3
"""
Application GUI unifiée pour la gestion de photos - Version refactorisée
Interface maître-détail avec gestion de fichiers de configuration JSON
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import copy
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
from typing import Dict, List, Optional, Any

# Import du support drag & drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("⚠️ tkinterdnd2 non disponible - fonctionnalité drag & drop désactivée")

# Import du calendrier
try:
    from tkcalendar import DateEntry
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False
    print("⚠️ tkcalendar non disponible - sélection de date par calendrier désactivée")

# Import des modules locaux
from photo_utils import ConfigManager, generate_map, parse_ville, generate_collage, generate_titre_jour

# Version de l'application
APP_VERSION = "1.0.0"


class ActionConfig:
    """Représente une configuration d'action (carte, collage ou titreJour)"""

    def __init__(self, action_type: str, name: str, params: Optional[Dict[str, Any]] = None, dirty: bool = False, checked: bool = False):
        """
        Initialise une configuration d'action

        Args:
            action_type: Type d'action ('carte', 'collage', 'titreJour')
            name: Nom de l'action (nom du fichier de sortie)
            params: Paramètres de configuration spécifiques au type
            dirty: Indique si la configuration a été modifiée depuis la dernière génération
            checked: Indique si la configuration est cochée pour génération
        """
        self.action_type = action_type
        self.name = name
        self.params = params or self._get_default_params(action_type)
        self.dirty = dirty
        self.checked = checked

    def _get_default_params(self, action_type: str) -> Dict[str, Any]:
        """Retourne les paramètres par défaut selon le type d'action"""
        if action_type == 'carte':
            return {
                'gpx_file': '',
                'title': '',
                'date': '',
                'start_time': '',
                'end_time': '',
                'cities': '',
                'margin': '',
                'ref_image': ''
            }
        elif action_type == 'collage':
            return {
                'title': '',
                'ref_image': '',
                'images': []
            }
        elif action_type == 'titreJour':
            return {
                'title': '',
                'date': '',
                'images': []
            }
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire"""
        return {
            'type': self.action_type,
            'name': self.name,
            'params': self.params,
            'dirty': self.dirty,
            'checked': self.checked
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ActionConfig':
        """Crée une ActionConfig depuis un dictionnaire"""
        return ActionConfig(
            action_type=data['type'],
            name=data['name'],
            params=data.get('params', {}),
            dirty=data.get('dirty', False),
            checked=data.get('checked', False)
        )


class PhotosApp:
    """Application principale pour la gestion de photos"""

    def __init__(self, root):
        """Initialise l'application"""
        self.root = root
        self.root.title(f"Photos Manager - Application Unifiée v{APP_VERSION}")

        # Gestionnaire de configuration
        self.config_manager = ConfigManager()

        # Liste des configurations d'actions
        self.actions: List[ActionConfig] = []

        # Configuration actuellement sélectionnée
        self.current_action: Optional[ActionConfig] = None

        # Fichier de configuration actuel
        self.current_file: Optional[str] = None

        # Suivi des modifications
        self.modified: bool = False

        # Date mémorisée pour initialiser les nouvelles configurations
        self.last_selected_date: Optional[str] = None

        # Restaurer la géométrie de la fenêtre
        geometry = self.config_manager.get("window_geometry", "1200x800")
        self.root.geometry(geometry)

        # Créer le menu
        self._create_menu()

        # Créer l'interface
        self._create_widgets()

        # Configurer le drag & drop
        self._setup_drag_drop()

        # Charger les paramètres sauvegardés
        self._load_settings()

        # Sauvegarder la géométrie en quittant
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_menu(self):
        """Crée le menu de l'application"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Nouveau", command=self._new_file)
        file_menu.add_separator()
        file_menu.add_command(label="Charger...", command=self._load_file)
        file_menu.add_command(label="Sauver", command=self._save_file)
        file_menu.add_command(label="Sauver Sous...", command=self._save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self._on_closing)

    def _create_widgets(self):
        """Crée les widgets de l'interface"""
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # PanedWindow horizontal pour séparer gauche/droite
        self.main_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Zone de gauche (1/3)
        self._create_left_panel()

        # Zone de droite (2/3)
        self._create_right_panel()

        # Ajouter les panels au PanedWindow
        self.main_paned.add(self.left_frame, weight=1)
        self.main_paned.add(self.right_frame, weight=2)

    def _create_left_panel(self):
        """Crée le panneau de gauche avec liste et contrôles"""
        self.left_frame = ttk.Frame(self.main_paned, padding="5")

        # PanedWindow vertical pour séparer liste/logs
        left_paned = ttk.PanedWindow(self.left_frame, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True)

        # Zone supérieure : liste et boutons
        top_frame = ttk.Frame(left_paned)

        # Liste des configurations
        list_label = ttk.Label(top_frame, text="Configurations :")
        list_label.pack(anchor=tk.W, pady=(0, 5))

        # Checkbox master pour tout cocher/décocher
        self.master_check_var = tk.BooleanVar(value=False)
        self.master_checkbox = ttk.Checkbutton(
            top_frame,
            text="Tout cocher/décocher",
            variable=self.master_check_var,
            command=self._toggle_all_checks
        )
        self.master_checkbox.pack(anchor=tk.W, pady=(0, 5))

        # Frame pour la liste avec scrollbar
        list_container = ttk.Frame(top_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        # Créer un Treeview pour afficher les configurations
        self.actions_tree = ttk.Treeview(list_container, columns=('check', 'name'),
                                         show='tree headings', selectmode='browse')
        self.actions_tree.heading('#0', text='Type')
        self.actions_tree.heading('check', text='☐')
        self.actions_tree.heading('name', text='Nom')
        self.actions_tree.column('#0', width=80)
        self.actions_tree.column('check', width=30, anchor='center')
        self.actions_tree.column('name', width=170)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL,
                                  command=self.actions_tree.yview)
        self.actions_tree.configure(yscrollcommand=scrollbar.set)

        self.actions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.actions_tree.bind('<<TreeviewSelect>>', self._on_action_select)
        # Bind clic pour toggle checkbox
        self.actions_tree.bind('<Button-1>', self._on_tree_click)

        # Boutons d'action - ligne 1
        buttons_frame1 = ttk.Frame(top_frame)
        buttons_frame1.pack(fill=tk.X, pady=(10, 2))

        ttk.Button(buttons_frame1, text="Ajouter",
                   command=self._add_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(buttons_frame1, text="Supprimer",
                   command=self._delete_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(buttons_frame1, text="↑",
                   command=self._move_action_up).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(buttons_frame1, text="↓",
                   command=self._move_action_down).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Boutons d'action - ligne 1.5
        buttons_frame1_5 = ttk.Frame(top_frame)
        buttons_frame1_5.pack(fill=tk.X, pady=(2, 2))

        ttk.Button(buttons_frame1_5, text="Renommer",
                   command=self._rename_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(buttons_frame1_5, text="Dupliquer",
                   command=self._duplicate_action).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Bouton génération - ligne 2
        ttk.Button(top_frame, text="Générer les images cochées",
                   command=self._generate_images).pack(fill=tk.X, pady=(0, 0))

        # Zone inférieure : logs
        log_frame = ttk.Frame(left_paned)

        ttk.Label(log_frame, text="Logs :").pack(anchor=tk.W, pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=40)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(log_frame, text="Effacer logs",
                   command=self._clear_logs).pack(fill=tk.X, pady=(5, 0))

        # Ajouter les frames au PanedWindow vertical
        left_paned.add(top_frame, weight=3)
        left_paned.add(log_frame, weight=1)

    def _create_right_panel(self):
        """Crée le panneau de droite pour les détails de configuration"""
        self.right_frame = ttk.Frame(self.main_paned, padding="5")

        # Label de titre
        self.detail_title = ttk.Label(self.right_frame, text="Sélectionnez une configuration",
                                      font=('TkDefaultFont', 12, 'bold'))
        self.detail_title.pack(anchor=tk.W, pady=(0, 10))

        # Container pour les différents formulaires
        self.detail_container = ttk.Frame(self.right_frame)
        self.detail_container.pack(fill=tk.BOTH, expand=True)

        # Créer les frames pour chaque type (cachés par défaut)
        self._create_carte_detail()
        self._create_collage_detail()
        self._create_titre_jour_detail()

    def _create_carte_detail(self):
        """Crée le formulaire de détail pour les cartes"""
        self.carte_frame = ttk.Frame(self.detail_container)

        row = 0
        # Fichier GPX
        ttk.Label(self.carte_frame, text="Fichier GPX :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_gpx_var = tk.StringVar()
        gpx_entry = ttk.Entry(self.carte_frame, textvariable=self.carte_gpx_var)
        gpx_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(self.carte_frame, text="...", width=5,
                   command=self._browse_gpx_file).grid(row=row, column=2)

        # Titre
        row += 1
        ttk.Label(self.carte_frame, text="Titre (optionnel) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_title_var = tk.StringVar()
        ttk.Entry(self.carte_frame, textvariable=self.carte_title_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Date
        row += 1
        ttk.Label(self.carte_frame, text="Date (YYYY-MM-DD) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_date_var = tk.StringVar()
        if HAS_CALENDAR:
            self.carte_date_entry = DateEntry(self.carte_frame, textvariable=self.carte_date_var,
                                              date_pattern='yyyy-mm-dd', width=20)
            self.carte_date_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
            self.carte_date_entry.bind('<<DateEntrySelected>>', self._on_date_selected)
        else:
            ttk.Entry(self.carte_frame, textvariable=self.carte_date_var).grid(
                row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Plage horaire
        row += 1
        ttk.Label(self.carte_frame, text="Heure début (HH:MM:SS) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_start_time_var = tk.StringVar()
        ttk.Entry(self.carte_frame, textvariable=self.carte_start_time_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        row += 1
        ttk.Label(self.carte_frame, text="Heure fin (HH:MM:SS) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_end_time_var = tk.StringVar()
        ttk.Entry(self.carte_frame, textvariable=self.carte_end_time_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Villes
        row += 1
        ttk.Label(self.carte_frame, text="Villes :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_cities_var = tk.StringVar()
        ttk.Entry(self.carte_frame, textvariable=self.carte_cities_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(self.carte_frame, text="(séparées par des virgules)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Marge
        row += 2
        ttk.Label(self.carte_frame, text="Marge (mètres) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_margin_var = tk.StringVar()
        ttk.Entry(self.carte_frame, textvariable=self.carte_margin_var).grid(
            row=row, column=1, sticky=tk.W, padx=(5, 5))

        # Image de référence
        row += 1
        ttk.Label(self.carte_frame, text="Image de référence :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.carte_ref_image_var = tk.StringVar()
        self.carte_ref_image_entry = ttk.Entry(self.carte_frame, textvariable=self.carte_ref_image_var)
        self.carte_ref_image_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(self.carte_frame, text="...", width=5,
                   command=self._browse_ref_image).grid(row=row, column=2)

        # Configuration du redimensionnement
        self.carte_frame.columnconfigure(1, weight=1)

    def _create_collage_detail(self):
        """Crée le formulaire de détail pour les collages"""
        self.collage_frame = ttk.Frame(self.detail_container)

        row = 0
        # Titre
        ttk.Label(self.collage_frame, text="Titre (optionnel) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_title_var = tk.StringVar()
        ttk.Entry(self.collage_frame, textvariable=self.collage_title_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Image de référence
        row += 1
        ttk.Label(self.collage_frame, text="Image de référence :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_ref_image_var = tk.StringVar()
        self.collage_ref_image_entry = ttk.Entry(self.collage_frame, textvariable=self.collage_ref_image_var)
        self.collage_ref_image_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(self.collage_frame, text="...", width=5,
                   command=self._browse_collage_ref_image).grid(row=row, column=2)
        ttk.Label(self.collage_frame, text="(optionnel - sinon utilise la photo la plus vieille)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Sélection des images
        row += 2
        ttk.Label(self.collage_frame, text="Images :").grid(row=row, column=0, sticky=tk.W, pady=2)
        btn_frame = ttk.Frame(self.collage_frame)
        btn_frame.grid(row=row, column=1, sticky=tk.W, padx=(5, 5), columnspan=2)
        ttk.Button(btn_frame, text="Ajouter", command=self._add_collage_images).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Supprimer photo sélectionnée", command=self._delete_collage_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Tout effacer", command=self._clear_collage_images).pack(side=tk.LEFT)

        # Liste des images
        row += 1
        list_frame = ttk.Frame(self.collage_frame)
        list_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))

        self.collage_images_listbox = tk.Listbox(list_frame, height=10)
        self.collage_images_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.collage_images_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.collage_images_listbox.configure(yscrollcommand=scrollbar.set)

        # Configuration du redimensionnement
        self.collage_frame.columnconfigure(1, weight=1)
        self.collage_frame.rowconfigure(row, weight=1)

    def _create_titre_jour_detail(self):
        """Crée le formulaire de détail pour les titres du jour"""
        self.titre_jour_frame = ttk.Frame(self.detail_container)

        row = 0
        # Titre
        ttk.Label(self.titre_jour_frame, text="Titre * :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.titre_jour_title_var = tk.StringVar()
        ttk.Entry(self.titre_jour_frame, textvariable=self.titre_jour_title_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Date
        row += 1
        ttk.Label(self.titre_jour_frame, text="Date (YYYY-MM-DD) * :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.titre_jour_date_var = tk.StringVar()
        if HAS_CALENDAR:
            self.titre_jour_date_entry = DateEntry(self.titre_jour_frame, textvariable=self.titre_jour_date_var,
                                                   date_pattern='yyyy-mm-dd', width=20)
            self.titre_jour_date_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
            self.titre_jour_date_entry.bind('<<DateEntrySelected>>', self._on_date_selected)
        else:
            ttk.Entry(self.titre_jour_frame, textvariable=self.titre_jour_date_var).grid(
                row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Sélection des images
        row += 1
        ttk.Label(self.titre_jour_frame, text="Images :").grid(row=row, column=0, sticky=tk.W, pady=2)
        btn_frame = ttk.Frame(self.titre_jour_frame)
        btn_frame.grid(row=row, column=1, sticky=tk.W, padx=(5, 5), columnspan=2)
        ttk.Button(btn_frame, text="Ajouter", command=self._add_titre_jour_images).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Supprimer photo sélectionnée", command=self._delete_titre_jour_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Tout effacer", command=self._clear_titre_jour_images).pack(side=tk.LEFT)

        # Liste des images
        row += 1
        list_frame = ttk.Frame(self.titre_jour_frame)
        list_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))

        self.titre_jour_images_listbox = tk.Listbox(list_frame, height=10)
        self.titre_jour_images_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.titre_jour_images_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.titre_jour_images_listbox.configure(yscrollcommand=scrollbar.set)

        # Configuration du redimensionnement
        self.titre_jour_frame.columnconfigure(1, weight=1)
        self.titre_jour_frame.rowconfigure(row, weight=1)

    # ========== Drag & Drop ==========

    def _setup_drag_drop(self):
        """Configure le drag & drop sur les widgets d'images"""
        if not HAS_DND:
            return

        # Drag & drop sur les Entry d'image de référence
        self._enable_drop_on_entry(self.carte_ref_image_entry, self.carte_ref_image_var)
        self._enable_drop_on_entry(self.collage_ref_image_entry, self.collage_ref_image_var)

        # Drag & drop sur les Listbox d'images (collage et titreJour)
        self._enable_drop_on_listbox(self.collage_images_listbox)
        self._enable_drop_on_listbox(self.titre_jour_images_listbox)

    def _enable_drop_on_entry(self, entry_widget, string_var):
        """Active le drag & drop sur un widget Entry"""
        if not HAS_DND:
            return

        entry_widget.drop_target_register(DND_FILES)
        entry_widget.dnd_bind('<<Drop>>', lambda e: self._on_drop_entry(e, string_var))

    def _enable_drop_on_listbox(self, listbox_widget):
        """Active le drag & drop sur un widget Listbox"""
        if not HAS_DND:
            return

        listbox_widget.drop_target_register(DND_FILES)
        listbox_widget.dnd_bind('<<Drop>>', lambda e: self._on_drop_listbox(e, listbox_widget))

    def _parse_dropped_files(self, data: str) -> List[str]:
        """Parse les fichiers droppés et filtre les images"""
        files = []

        # Le format de data peut varier selon les systèmes
        # Généralement, c'est une chaîne avec des chemins séparés par des espaces
        # et les chemins avec espaces sont entre accolades {}
        if data.startswith('{'):
            # Format avec accolades
            import re
            files = re.findall(r'\{([^}]+)\}', data)
            # Aussi ajouter les fichiers sans accolades
            remaining = re.sub(r'\{[^}]+\}', '', data).strip()
            if remaining:
                files.extend(remaining.split())
        else:
            # Format simple avec espaces
            files = data.split()

        # Filtrer uniquement les fichiers images
        image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
        image_files = [f for f in files if os.path.isfile(f) and f.lower().endswith(image_extensions)]

        return image_files

    def _on_drop_entry(self, event, string_var):
        """Gère le drop sur un Entry (pour l'image de référence)"""
        files = self._parse_dropped_files(event.data)

        if files:
            # Prendre seulement le premier fichier
            string_var.set(files[0])
            self._log(f"📎 Image ajoutée par drag & drop : {os.path.basename(files[0])}")
        else:
            messagebox.showwarning("Attention", "Aucun fichier image valide détecté")

        return event.action

    def _on_drop_listbox(self, event, listbox_widget):
        """Gère le drop sur une Listbox (pour les listes d'images)"""
        files = self._parse_dropped_files(event.data)

        if files:
            # Récupérer les fichiers déjà présents
            existing_items = list(listbox_widget.get(0, tk.END))

            # Ajouter les nouveaux fichiers s'ils ne sont pas déjà présents
            added_count = 0
            for file in files:
                if file not in existing_items:
                    listbox_widget.insert(tk.END, file)
                    added_count += 1

            if added_count > 0:
                self._log(f"📎 {added_count} image(s) ajoutée(s) par drag & drop")
            else:
                self._log("ℹ️ Toutes les images sont déjà dans la liste")
        else:
            messagebox.showwarning("Attention", "Aucun fichier image valide détecté")

        return event.action

    # ========== Gestion des fichiers ==========

    def _new_file(self):
        """Crée un nouveau fichier de configuration"""
        if self._check_unsaved_changes():
            self.actions = []
            self.current_action = None
            self.current_file = None
            self.modified = False
            self._refresh_actions_list()
            self._show_detail_panel(None)
            self._log("Nouveau fichier créé")

    def _load_file(self):
        """Charge un fichier de configuration"""
        if not self._check_unsaved_changes():
            return

        filename = filedialog.askopenfilename(
            title="Charger un fichier de configuration",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Vérifier et convertir la version si nécessaire
                version = data.get('version', 1)
                if version != 2:
                    self._log(f"Conversion du fichier de version {version} vers version 2")
                    # Ici on pourrait faire des conversions si nécessaire

                # Charger les configurations
                self.actions = [ActionConfig.from_dict(item) for item in data.get('actions', [])]
                self.current_file = filename
                self.modified = False

                # Charger la date mémorisée
                self.last_selected_date = data.get('last_selected_date', None)

                self._refresh_actions_list()
                self._log(f"Fichier chargé : {filename}")

            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors du chargement : {str(e)}")

    def _save_file(self):
        """Sauvegarde le fichier de configuration"""
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self._save_file_as()

    def _save_file_as(self):
        """Sauvegarde le fichier de configuration sous un nouveau nom"""
        filename = filedialog.asksaveasfilename(
            title="Sauvegarder sous",
            defaultextension=".json",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")]
        )

        if filename:
            self._save_to_file(filename)
            self.current_file = filename

    def _save_to_file(self, filename: str):
        """Sauvegarde les configurations dans un fichier"""
        # Sauvegarder la configuration actuelle d'abord
        self._save_current_action()

        try:
            data = {
                'version': 2,
                'actions': [action.to_dict() for action in self.actions],
                'last_selected_date': self.last_selected_date
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.modified = False
            self._log(f"Fichier sauvegardé : {filename}")

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la sauvegarde : {str(e)}")

    def _check_unsaved_changes(self) -> bool:
        """Vérifie s'il y a des changements non sauvegardés"""
        if self.modified:
            response = messagebox.askyesnocancel(
                "Modifications non sauvegardées",
                "Voulez-vous sauvegarder les modifications ?"
            )
            if response is None:  # Cancel
                return False
            elif response:  # Yes
                self._save_file()
        return True

    # ========== Gestion de la liste d'actions ==========

    def _refresh_actions_list(self, keep_selection=False):
        """Rafraîchit l'affichage de la liste des actions

        Args:
            keep_selection: Si True, conserve la sélection actuelle après le rafraîchissement
        """
        # Sauvegarder la sélection actuelle si nécessaire
        selected_index = None
        if keep_selection:
            selection = self.actions_tree.selection()
            if selection:
                selected_index = self.actions_tree.index(selection[0])

        # Vider la liste
        for item in self.actions_tree.get_children():
            self.actions_tree.delete(item)

        # Ajouter les actions
        for action in self.actions:
            type_label = self._get_action_type_label(action.action_type)
            # Ajouter "*" avant le nom si la configuration est dirty
            display_name = f"* {action.name}" if action.dirty else action.name
            # Afficher ☑ si coché, ☐ sinon
            check_symbol = '☑' if action.checked else '☐'
            self.actions_tree.insert('', 'end', text=type_label,
                                    values=(check_symbol, display_name), tags=(action.action_type,))

        # Restaurer la sélection si nécessaire
        if keep_selection and selected_index is not None:
            items = self.actions_tree.get_children()
            if selected_index < len(items):
                self.actions_tree.selection_set(items[selected_index])

    def _get_action_type_label(self, action_type: str) -> str:
        """Retourne le label pour le type d'action"""
        labels = {
            'carte': 'Carte',
            'collage': 'Collage',
            'titreJour': 'Titre jour'
        }
        return labels.get(action_type, 'Inconnu')

    def _toggle_all_checks(self):
        """Coche/décoche toutes les configurations"""
        check_all = self.master_check_var.get()
        for action in self.actions:
            action.checked = check_all
        self.modified = True
        self._refresh_actions_list(keep_selection=True)

    def _on_tree_click(self, event):
        """Gère le clic sur le Treeview pour toggler les checkboxes"""
        # Identifier la région cliquée
        region = self.actions_tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        # Identifier la colonne
        column = self.actions_tree.identify_column(event.x)

        # Si c'est la colonne checkbox (colonne #1)
        if column == '#1':
            # Identifier l'item cliqué
            item = self.actions_tree.identify_row(event.y)
            if item:
                # Récupérer l'index de l'action
                index = self.actions_tree.index(item)
                # Toggler le checkbox
                self.actions[index].checked = not self.actions[index].checked
                self.modified = True
                self._refresh_actions_list(keep_selection=True)

    def _add_action(self):
        """Ajoute une nouvelle action"""
        # Créer une fenêtre de dialogue
        dialog = tk.Toplevel(self.root)
        dialog.title("Nouvelle action")
        dialog.transient(self.root)
        dialog.grab_set()

        # Type
        ttk.Label(dialog, text="Type :").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        type_var = tk.StringVar(value='carte')
        type_combo = ttk.Combobox(dialog, textvariable=type_var,
                                  values=['carte', 'collage', 'titreJour'],
                                  state='readonly', width=20)
        type_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)

        # Nom
        ttk.Label(dialog, text="Nom :").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=23)
        name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        name_entry.focus()

        # Boutons
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        def on_ok():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Erreur", "Veuillez saisir un nom", parent=dialog)
                return

            # Vérifier qu'il n'y a pas déjà une action avec ce nom
            for action in self.actions:
                if action.name == name:
                    messagebox.showerror("Erreur", f"Une configuration avec le nom '{name}' existe déjà", parent=dialog)
                    return

            # Créer la nouvelle action avec dirty=True et checked=True
            action = ActionConfig(type_var.get(), name, dirty=True, checked=True)

            # Initialiser les champs de date avec la date mémorisée si disponible
            if self.last_selected_date:
                if action.action_type == 'carte':
                    action.params['date'] = self.last_selected_date
                elif action.action_type == 'titreJour':
                    action.params['date'] = self.last_selected_date

            self.actions.append(action)
            self.modified = True
            self._refresh_actions_list()
            dialog.destroy()

            # Sélectionner la nouvelle action
            items = self.actions_tree.get_children()
            if items:
                self.actions_tree.selection_set(items[-1])
                self._on_action_select(None)

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Annuler", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Enter pour valider
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        # Centrer la fenêtre
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')

    def _delete_action(self):
        """Supprime l'action sélectionnée"""
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action à supprimer")
            return

        # Confirmer la suppression
        if not messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer cette action ?"):
            return

        # Récupérer l'index de l'action
        item = selection[0]
        index = self.actions_tree.index(item)

        # Supprimer l'action
        del self.actions[index]
        self.modified = True
        self._refresh_actions_list()
        self.current_action = None
        self._show_detail_panel(None)

    def _move_action_up(self):
        """Déplace l'action sélectionnée vers le haut"""
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action à déplacer")
            return

        # Récupérer l'index de l'action
        item = selection[0]
        index = self.actions_tree.index(item)

        if index == 0:
            return  # Déjà en haut

        # Échanger avec l'élément précédent
        self.actions[index], self.actions[index - 1] = self.actions[index - 1], self.actions[index]
        self.modified = True
        self._refresh_actions_list()

        # Resélectionner l'élément
        items = self.actions_tree.get_children()
        self.actions_tree.selection_set(items[index - 1])

    def _move_action_down(self):
        """Déplace l'action sélectionnée vers le bas"""
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action à déplacer")
            return

        # Récupérer l'index de l'action
        item = selection[0]
        index = self.actions_tree.index(item)

        if index == len(self.actions) - 1:
            return  # Déjà en bas

        # Échanger avec l'élément suivant
        self.actions[index], self.actions[index + 1] = self.actions[index + 1], self.actions[index]
        self.modified = True
        self._refresh_actions_list()

        # Resélectionner l'élément
        items = self.actions_tree.get_children()
        self.actions_tree.selection_set(items[index + 1])

    def _rename_action(self):
        """Renomme l'action sélectionnée"""
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action à renommer")
            return

        # Récupérer l'index de l'action
        item = selection[0]
        index = self.actions_tree.index(item)
        action = self.actions[index]

        # Créer une fenêtre de dialogue
        dialog = tk.Toplevel(self.root)
        dialog.title("Renommer l'action")
        dialog.transient(self.root)
        dialog.grab_set()

        # Nom actuel
        ttk.Label(dialog, text="Nom actuel :").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(dialog, text=action.name, font=('TkDefaultFont', 10, 'bold')).grid(
            row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Nouveau nom
        ttk.Label(dialog, text="Nouveau nom :").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        name_var = tk.StringVar(value=action.name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        name_entry.focus()
        name_entry.select_range(0, tk.END)

        # Boutons
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        def on_ok():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Erreur", "Veuillez saisir un nom", parent=dialog)
                return

            # Vérifier qu'il n'y a pas déjà une autre action avec ce nom
            for i, other_action in enumerate(self.actions):
                if i != index and other_action.name == new_name:
                    messagebox.showerror("Erreur", f"Une configuration avec le nom '{new_name}' existe déjà", parent=dialog)
                    return

            # Renommer le fichier image si nécessaire
            old_name = action.name
            if self.current_file and old_name != new_name:
                target_folder = os.path.dirname(self.current_file)
                old_image_path = os.path.join(target_folder, f"{old_name}.jpg")
                new_image_path = os.path.join(target_folder, f"{new_name}.jpg")

                # Si l'ancien fichier image existe
                if os.path.exists(old_image_path):
                    # Vérifier si le nouveau fichier existe déjà
                    if os.path.exists(new_image_path):
                        messagebox.showerror("Erreur",
                            f"Impossible de renommer l'image : le fichier '{new_name}.jpg' existe déjà",
                            parent=dialog)
                        return

                    try:
                        # Renommer le fichier image
                        os.rename(old_image_path, new_image_path)
                        self._log(f"Image renommée : {old_name}.jpg → {new_name}.jpg")
                    except Exception as e:
                        messagebox.showerror("Erreur",
                            f"Erreur lors du renommage de l'image : {str(e)}",
                            parent=dialog)
                        return

            # Renommer l'action
            action.name = new_name
            self.modified = True
            self._refresh_actions_list()

            # Resélectionner l'élément renommé
            items = self.actions_tree.get_children()
            self.actions_tree.selection_set(items[index])

            # Mettre à jour le titre du panneau de détail
            if self.current_action == action:
                type_label = self._get_action_type_label(action.action_type)
                self.detail_title.config(text=f"{type_label} - {action.name}")

            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Annuler", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Enter pour valider
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        # Centrer la fenêtre
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')

    def _duplicate_action(self):
        """Duplique l'action sélectionnée"""
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action à dupliquer")
            return

        # Récupérer l'index de l'action
        item = selection[0]
        index = self.actions_tree.index(item)
        action = self.actions[index]

        # Sauvegarder la configuration actuelle avant de dupliquer
        self._save_current_action()

        # Créer une fenêtre de dialogue pour le nouveau nom
        dialog = tk.Toplevel(self.root)
        dialog.title("Dupliquer l'action")
        dialog.transient(self.root)
        dialog.grab_set()

        # Configuration source
        ttk.Label(dialog, text="Configuration source :").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(dialog, text=action.name, font=('TkDefaultFont', 10, 'bold')).grid(
            row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Nouveau nom
        ttk.Label(dialog, text="Nouveau nom :").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        name_var = tk.StringVar(value=action.name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
        name_entry.focus()
        name_entry.select_range(0, tk.END)

        # Boutons
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        def on_ok():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Erreur", "Veuillez saisir un nom", parent=dialog)
                return

            # Vérifier qu'il n'y a pas déjà une action avec ce nom
            for other_action in self.actions:
                if other_action.name == new_name:
                    messagebox.showerror("Erreur", f"Une configuration avec le nom '{new_name}' existe déjà", parent=dialog)
                    return

            # Créer une copie de l'action avec le nouveau nom
            # On copie les paramètres en profondeur pour éviter les références partagées
            new_action = ActionConfig(
                action_type=action.action_type,
                name=new_name,
                params=copy.deepcopy(action.params),
                dirty=True,
                checked=True
            )

            # Ajouter la nouvelle action juste après l'action dupliquée
            self.actions.insert(index + 1, new_action)
            self.modified = True
            self._refresh_actions_list()

            # Sélectionner la nouvelle action
            items = self.actions_tree.get_children()
            self.actions_tree.selection_set(items[index + 1])
            self._on_action_select(None)

            self._log(f"Configuration '{action.name}' dupliquée sous le nom '{new_name}'")

            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Annuler", command=on_cancel).pack(side=tk.LEFT, padx=5)

        # Enter pour valider
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        # Centrer la fenêtre
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')

    def _on_action_select(self, event):
        """Appelé quand une action est sélectionnée"""
        selection = self.actions_tree.selection()
        if not selection:
            return

        # Sauvegarder la configuration actuelle
        self._save_current_action()

        # Récupérer l'action sélectionnée
        item = selection[0]
        index = self.actions_tree.index(item)
        action = self.actions[index]

        self.current_action = action
        self._show_detail_panel(action)

    def _show_detail_panel(self, action: Optional[ActionConfig]):
        """Affiche le panneau de détail pour l'action donnée"""
        # Cacher tous les frames
        self.carte_frame.pack_forget()
        self.collage_frame.pack_forget()
        self.titre_jour_frame.pack_forget()

        if action is None:
            self.detail_title.config(text="Sélectionnez une configuration")
            return

        # Mettre à jour le titre
        type_label = self._get_action_type_label(action.action_type)
        self.detail_title.config(text=f"{type_label} - {action.name}")

        # Afficher le bon frame et charger les données
        if action.action_type == 'carte':
            self._load_carte_params(action.params)
            self.carte_frame.pack(fill=tk.BOTH, expand=True)
        elif action.action_type == 'collage':
            self._load_collage_params(action.params)
            self.collage_frame.pack(fill=tk.BOTH, expand=True)
        elif action.action_type == 'titreJour':
            self._load_titre_jour_params(action.params)
            self.titre_jour_frame.pack(fill=tk.BOTH, expand=True)

    def _save_current_action(self):
        """Sauvegarde les paramètres de l'action actuelle"""
        if self.current_action is None:
            return

        self.modified = True

        # Sauvegarder les anciens paramètres pour comparaison
        old_params = copy.deepcopy(self.current_action.params)
        old_dirty = self.current_action.dirty

        if self.current_action.action_type == 'carte':
            self.current_action.params = {
                'gpx_file': self.carte_gpx_var.get(),
                'title': self.carte_title_var.get(),
                'date': self.carte_date_var.get(),
                'start_time': self.carte_start_time_var.get(),
                'end_time': self.carte_end_time_var.get(),
                'cities': self.carte_cities_var.get(),
                'margin': self.carte_margin_var.get(),
                'ref_image': self.carte_ref_image_var.get()
            }
        elif self.current_action.action_type == 'collage':
            images = []
            for i in range(self.collage_images_listbox.size()):
                images.append(self.collage_images_listbox.get(i))

            self.current_action.params = {
                'title': self.collage_title_var.get(),
                'ref_image': self.collage_ref_image_var.get(),
                'images': images
            }
        elif self.current_action.action_type == 'titreJour':
            images = []
            for i in range(self.titre_jour_images_listbox.size()):
                images.append(self.titre_jour_images_listbox.get(i))

            self.current_action.params = {
                'title': self.titre_jour_title_var.get(),
                'date': self.titre_jour_date_var.get(),
                'images': images
            }

        # Marquer comme dirty si les paramètres ont changé
        if old_params != self.current_action.params:
            self.current_action.dirty = True
            # Cocher automatiquement la configuration quand elle devient dirty
            if not old_dirty:  # Si elle n'était pas dirty avant
                self.current_action.checked = True

            # Rafraîchir la liste si le statut dirty a changé, sans désélectionner
            if old_dirty != self.current_action.dirty:
                self._refresh_actions_list(keep_selection=True)

    def _load_carte_params(self, params: Dict[str, Any]):
        """Charge les paramètres d'une carte"""
        self.carte_gpx_var.set(params.get('gpx_file', ''))
        self.carte_title_var.set(params.get('title', ''))
        self.carte_date_var.set(params.get('date', ''))
        self.carte_start_time_var.set(params.get('start_time', ''))
        self.carte_end_time_var.set(params.get('end_time', ''))
        self.carte_cities_var.set(params.get('cities', ''))
        self.carte_margin_var.set(params.get('margin', ''))
        self.carte_ref_image_var.set(params.get('ref_image', ''))

    def _load_collage_params(self, params: Dict[str, Any]):
        """Charge les paramètres d'un collage"""
        self.collage_title_var.set(params.get('title', ''))
        self.collage_ref_image_var.set(params.get('ref_image', ''))

        # Charger les images
        self.collage_images_listbox.delete(0, tk.END)
        for img in params.get('images', []):
            self.collage_images_listbox.insert(tk.END, img)

    def _load_titre_jour_params(self, params: Dict[str, Any]):
        """Charge les paramètres d'un titre du jour"""
        self.titre_jour_title_var.set(params.get('title', ''))
        self.titre_jour_date_var.set(params.get('date', ''))

        # Charger les images
        self.titre_jour_images_listbox.delete(0, tk.END)
        for img in params.get('images', []):
            self.titre_jour_images_listbox.insert(tk.END, img)

    # ========== Gestion des images ==========

    def _add_collage_images(self):
        """Ajoute des images au collage"""
        initial_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les images",
            initialdir=initial_dir,
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )

        for filename in filenames:
            # Vérifier si l'image n'est pas déjà dans la liste
            items = list(self.collage_images_listbox.get(0, tk.END))
            if filename not in items:
                self.collage_images_listbox.insert(tk.END, filename)

    def _clear_collage_images(self):
        """Efface les images du collage"""
        self.collage_images_listbox.delete(0, tk.END)

    def _delete_collage_image(self):
        """Supprime l'image sélectionnée du collage"""
        selection = self.collage_images_listbox.curselection()
        if selection:
            self.collage_images_listbox.delete(selection[0])
        else:
            messagebox.showwarning("Attention", "Veuillez sélectionner une image à supprimer")

    def _add_titre_jour_images(self):
        """Ajoute des images au titre du jour"""
        initial_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les images",
            initialdir=initial_dir,
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )

        for filename in filenames:
            # Vérifier si l'image n'est pas déjà dans la liste
            items = list(self.titre_jour_images_listbox.get(0, tk.END))
            if filename not in items:
                self.titre_jour_images_listbox.insert(tk.END, filename)

    def _clear_titre_jour_images(self):
        """Efface les images du titre du jour"""
        self.titre_jour_images_listbox.delete(0, tk.END)

    def _delete_titre_jour_image(self):
        """Supprime l'image sélectionnée du titre du jour"""
        selection = self.titre_jour_images_listbox.curselection()
        if selection:
            self.titre_jour_images_listbox.delete(selection[0])
        else:
            messagebox.showwarning("Attention", "Veuillez sélectionner une image à supprimer")

    # ========== Parcourir les fichiers ==========

    def _browse_gpx_file(self):
        """Ouvre un dialogue pour sélectionner le fichier GPX"""
        initial_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        filename = filedialog.askopenfilename(
            title="Sélectionner le fichier GPX",
            initialdir=initial_dir,
            filetypes=[("Fichiers GPX", "*.gpx"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.carte_gpx_var.set(filename)

    def _browse_ref_image(self):
        """Ouvre un dialogue pour sélectionner l'image de référence (carte)"""
        initial_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        filename = filedialog.askopenfilename(
            title="Sélectionner l'image de référence",
            initialdir=initial_dir,
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.carte_ref_image_var.set(filename)

    def _browse_collage_ref_image(self):
        """Ouvre un dialogue pour sélectionner l'image de référence (collage)"""
        initial_dir = os.path.dirname(self.current_file) if self.current_file else os.getcwd()
        filename = filedialog.askopenfilename(
            title="Sélectionner l'image de référence",
            initialdir=initial_dir,
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.collage_ref_image_var.set(filename)

    def _on_date_selected(self, event):
        """Appelé quand une date est sélectionnée dans un calendrier"""
        # Récupérer la date sélectionnée (au format YYYY-MM-DD)
        date_str = event.widget.get()
        if date_str:
            self.last_selected_date = date_str
            self._log(f"📅 Date mémorisée : {date_str}")

    # ========== Génération ==========

    def _generate_images(self):
        """Génère les images pour toutes les actions cochées"""
        # Vérifier que le fichier est sauvegardé
        if not self.current_file:
            messagebox.showerror("Erreur", "Veuillez d'abord sauvegarder le fichier de configuration")
            return

        # Sauvegarder les paramètres actuels
        self._save_current_action()

        # Récupérer toutes les actions cochées
        checked_actions = [action for action in self.actions if action.checked]

        if not checked_actions:
            messagebox.showwarning("Attention", "Aucune configuration n'est cochée")
            return

        self._log(f"=== Génération de {len(checked_actions)} image(s) cochée(s) ===")

        # Générer chaque action cochée
        for action in checked_actions:
            self._generate_single_action(action)

        self._log("=== Génération terminée pour toutes les images cochées ===")

    def _generate_single_action(self, action: ActionConfig):
        """Génère l'image pour une action donnée"""
        # Lancer la génération selon le type
        if action.action_type == 'carte':
            self._generate_carte(action)
        elif action.action_type == 'collage':
            self._generate_collage(action)
        elif action.action_type == 'titreJour':
            self._generate_titre_jour(action)

    def _generate_carte(self, action: ActionConfig):
        """Génère une carte"""
        params = action.params

        # Vérifier les champs obligatoires
        if not params.get('gpx_file'):
            self._log(f"❌ Erreur pour '{action.name}': Veuillez sélectionner un fichier GPX")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_carte_thread, args=(action,))
        thread.start()

    def _generate_carte_thread(self, action: ActionConfig):
        """Génère la carte (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération de la carte '{action.name}'...")

            params = action.params

            # Récupérer les paramètres
            gpx_file = params.get('gpx_file')
            titre = params.get('title') or None
            date_str = params.get('date')
            start_time_str = params.get('start_time')
            end_time_str = params.get('end_time')
            cities_str = params.get('cities')
            margin_str = params.get('margin')
            ref_image = params.get('ref_image') or None

            # Parser les villes
            city_list = []
            if cities_str:
                for city in cities_str.split(','):
                    city = city.strip()
                    if city:
                        city_list.append(parse_ville(city))

            # Parser la marge
            marge = None
            if margin_str:
                try:
                    marge = int(margin_str)
                except ValueError:
                    self._log("⚠ Marge invalide, utilisation de la valeur automatique")

            # Parser la date/heure
            start_time = None
            end_time = None
            tz_france = ZoneInfo("Europe/Paris")

            if date_str:
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    start_time = date.replace(hour=0, minute=0, second=0, tzinfo=tz_france)
                    end_time = date.replace(hour=23, minute=59, second=59, tzinfo=tz_france)

                    # Ajouter les heures si spécifiées
                    if start_time_str:
                        time_parts = start_time_str.split(':')
                        start_time = start_time.replace(
                            hour=int(time_parts[0]),
                            minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                            second=int(time_parts[2]) if len(time_parts) > 2 else 0
                        )
                    if end_time_str:
                        time_parts = end_time_str.split(':')
                        end_time = end_time.replace(
                            hour=int(time_parts[0]),
                            minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                            second=int(time_parts[2]) if len(time_parts) > 2 else 0
                        )
                except ValueError as e:
                    self._log(f"⚠ Erreur de format de date : {e}")
                    raise

            # Changer vers le dossier du fichier JSON
            target_folder = os.path.dirname(self.current_file)
            if target_folder:
                os.chdir(target_folder)

            # Générer la carte
            generate_map(
                gpx_file, start_time, end_time, city_list,
                action.name, ref_image, marge, titre,
                log_callback=self._log
            )

            # Marquer la configuration comme non-dirty après génération réussie
            action.dirty = False
            # Décocher automatiquement quand dirty est mis à false
            action.checked = False
            self.root.after(0, self._refresh_actions_list)

            self._log(f"✅ Génération de '{action.name}' terminée avec succès !")

        except Exception as e:
            self._log(f"❌ Erreur pour '{action.name}': {str(e)}")

    def _generate_collage(self, action: ActionConfig):
        """Génère un collage"""
        params = action.params
        images = params.get('images', [])

        # Vérifier qu'il y a des images
        if len(images) < 2:
            self._log(f"❌ Erreur pour '{action.name}': Veuillez sélectionner au moins 2 images")
            return
        if len(images) > 7:
            self._log(f"❌ Erreur pour '{action.name}': Maximum 7 images autorisées")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_collage_thread, args=(action,))
        thread.start()

    def _generate_collage_thread(self, action: ActionConfig):
        """Génère le collage (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération du collage '{action.name}'...")

            params = action.params

            # Récupérer les paramètres
            title = params.get('title') or None
            ref_image = params.get('ref_image') or None
            images = params.get('images', [])

            # Changer vers le dossier du fichier JSON
            target_folder = os.path.dirname(self.current_file)
            if target_folder:
                os.chdir(target_folder)

            # Générer le collage
            output_file = generate_collage(
                images,
                title=title,
                ref_image=ref_image,
                output_name=action.name,
                log_callback=self._log
            )

            # Marquer la configuration comme non-dirty après génération réussie
            action.dirty = False
            # Décocher automatiquement quand dirty est mis à false
            action.checked = False
            self.root.after(0, self._refresh_actions_list)

            self._log(f"✅ Collage généré : {output_file}")

        except Exception as e:
            self._log(f"❌ Erreur pour '{action.name}': {str(e)}")

    def _generate_titre_jour(self, action: ActionConfig):
        """Génère un titre du jour"""
        params = action.params
        images = params.get('images', [])

        # Vérifier les champs obligatoires
        if not params.get('title'):
            self._log(f"❌ Erreur pour '{action.name}': Veuillez saisir un titre")
            return
        if not params.get('date'):
            self._log(f"❌ Erreur pour '{action.name}': Veuillez saisir une date")
            return
        if len(images) < 2:
            self._log(f"❌ Erreur pour '{action.name}': Veuillez sélectionner au moins 2 images")
            return
        if len(images) > 7:
            self._log(f"❌ Erreur pour '{action.name}': Maximum 7 images autorisées")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_titre_jour_thread, args=(action,))
        thread.start()

    def _generate_titre_jour_thread(self, action: ActionConfig):
        """Génère le titre du jour (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération du titre du jour '{action.name}'...")

            params = action.params

            # Récupérer les paramètres
            title = params.get('title')
            date_str = params.get('date')
            images = params.get('images', [])

            # Valider le format de date
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Le format de date doit être YYYY-MM-DD")

            # Changer vers le dossier du fichier JSON
            target_folder = os.path.dirname(self.current_file)
            if target_folder:
                os.chdir(target_folder)

            # Générer le titre du jour
            output_file = generate_titre_jour(
                images,
                date_str=date_str,
                title=title,
                output_name=action.name,
                log_callback=self._log
            )

            # Marquer la configuration comme non-dirty après génération réussie
            action.dirty = False
            # Décocher automatiquement quand dirty est mis à false
            action.checked = False
            self.root.after(0, self._refresh_actions_list)

            self._log(f"✅ Titre du jour généré : {output_file}")

        except Exception as e:
            self._log(f"❌ Erreur pour '{action.name}': {str(e)}")

    # ========== Logs ==========

    def _log(self, message: str):
        """Ajoute un message au log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_logs(self):
        """Efface les logs"""
        self.log_text.delete(1.0, tk.END)

    # ========== Paramètres ==========

    def _load_settings(self):
        """Charge les paramètres sauvegardés"""
        pass  # Plus de paramètres à charger

    def _on_closing(self):
        """Gère la fermeture de l'application"""
        # Vérifier les modifications non sauvegardées
        if not self._check_unsaved_changes():
            return

        # Sauvegarder la géométrie de la fenêtre
        self.config_manager.set("window_geometry", self.root.geometry())

        self.root.destroy()


def main():
    """Point d'entrée principal de l'application"""
    # Utiliser TkinterDnD.Tk si disponible pour le support drag & drop
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = PhotosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
