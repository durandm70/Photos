#!/usr/bin/env python3
"""
Application GUI unifiée pour la gestion de photos - Version refactorisée
Interface maître-détail avec gestion de fichiers de configuration JSON
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
from typing import Dict, List, Optional, Any

# Import des modules locaux
from photo_utils import ConfigManager, generate_map, parse_ville, generate_collage, generate_titre_jour


class ActionConfig:
    """Représente une configuration d'action (carte, collage ou titreJour)"""

    def __init__(self, action_type: str, name: str, params: Optional[Dict[str, Any]] = None):
        """
        Initialise une configuration d'action

        Args:
            action_type: Type d'action ('carte', 'collage', 'titreJour')
            name: Nom de l'action (nom du fichier de sortie)
            params: Paramètres de configuration spécifiques au type
        """
        self.action_type = action_type
        self.name = name
        self.params = params or self._get_default_params(action_type)

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
                'date': '',
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
            'params': self.params
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ActionConfig':
        """Crée une ActionConfig depuis un dictionnaire"""
        return ActionConfig(
            action_type=data['type'],
            name=data['name'],
            params=data.get('params', {})
        )


class PhotosApp:
    """Application principale pour la gestion de photos"""

    def __init__(self, root):
        """Initialise l'application"""
        self.root = root
        self.root.title("Photos Manager - Application Unifiée")

        # Gestionnaire de configuration
        self.config_manager = ConfigManager()

        # Liste des configurations d'actions
        self.actions: List[ActionConfig] = []

        # Configuration actuellement sélectionnée
        self.current_action: Optional[ActionConfig] = None

        # Fichier de configuration actuel
        self.current_file: Optional[str] = None

        # Restaurer la géométrie de la fenêtre
        geometry = self.config_manager.get("window_geometry", "1200x800")
        self.root.geometry(geometry)

        # Créer le menu
        self._create_menu()

        # Créer l'interface
        self._create_widgets()

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

        # Section dossier cible (en haut)
        self._create_target_folder_section(main_frame)

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

    def _create_target_folder_section(self, parent):
        """Crée la section de sélection du dossier cible"""
        folder_frame = ttk.LabelFrame(parent, text="Dossier cible", padding="10")
        folder_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(folder_frame, text="Dossier :").pack(side=tk.LEFT)

        self.target_folder_var = tk.StringVar()
        folder_entry = ttk.Entry(folder_frame, textvariable=self.target_folder_var)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        browse_btn = ttk.Button(folder_frame, text="...", width=5,
                                command=self._browse_target_folder)
        browse_btn.pack(side=tk.LEFT)

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

        # Frame pour la liste avec scrollbar
        list_container = ttk.Frame(top_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        # Créer un Treeview pour afficher les configurations avec icônes
        self.actions_tree = ttk.Treeview(list_container, columns=('name',),
                                         show='tree', selectmode='browse')
        self.actions_tree.heading('#0', text='Type')
        self.actions_tree.column('#0', width=100)

        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL,
                                  command=self.actions_tree.yview)
        self.actions_tree.configure(yscrollcommand=scrollbar.set)

        self.actions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.actions_tree.bind('<<TreeviewSelect>>', self._on_action_select)

        # Boutons d'action
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(buttons_frame, text="Ajouter",
                   command=self._add_action).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Supprimer",
                   command=self._delete_action).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Générer l'image",
                   command=self._generate_image).pack(fill=tk.X, pady=2)

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
        ttk.Entry(self.carte_frame, textvariable=self.carte_ref_image_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
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

        # Date
        row += 1
        ttk.Label(self.collage_frame, text="Date (YYYY-MM-DD) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_date_var = tk.StringVar()
        ttk.Entry(self.collage_frame, textvariable=self.collage_date_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Sélection des images
        row += 1
        ttk.Label(self.collage_frame, text="Images :").grid(row=row, column=0, sticky=tk.W, pady=2)
        btn_frame = ttk.Frame(self.collage_frame)
        btn_frame.grid(row=row, column=1, sticky=tk.W, padx=(5, 5), columnspan=2)
        ttk.Button(btn_frame, text="Ajouter", command=self._add_collage_images).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Effacer", command=self._clear_collage_images).pack(side=tk.LEFT)

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
        ttk.Entry(self.titre_jour_frame, textvariable=self.titre_jour_date_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Sélection des images
        row += 1
        ttk.Label(self.titre_jour_frame, text="Images :").grid(row=row, column=0, sticky=tk.W, pady=2)
        btn_frame = ttk.Frame(self.titre_jour_frame)
        btn_frame.grid(row=row, column=1, sticky=tk.W, padx=(5, 5), columnspan=2)
        ttk.Button(btn_frame, text="Ajouter", command=self._add_titre_jour_images).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Effacer", command=self._clear_titre_jour_images).pack(side=tk.LEFT)

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

    # ========== Gestion des fichiers ==========

    def _new_file(self):
        """Crée un nouveau fichier de configuration"""
        if self._check_unsaved_changes():
            self.actions = []
            self.current_action = None
            self.current_file = None
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

                # Charger les configurations
                self.actions = [ActionConfig.from_dict(item) for item in data.get('actions', [])]
                self.current_file = filename

                # Charger le dossier cible s'il existe
                if 'target_folder' in data:
                    self.target_folder_var.set(data['target_folder'])

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
                'target_folder': self.target_folder_var.get(),
                'actions': [action.to_dict() for action in self.actions]
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self._log(f"Fichier sauvegardé : {filename}")

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la sauvegarde : {str(e)}")

    def _check_unsaved_changes(self) -> bool:
        """Vérifie s'il y a des changements non sauvegardés"""
        # Pour l'instant, on retourne toujours True
        # TODO: implémenter la détection des changements
        return True

    # ========== Gestion de la liste d'actions ==========

    def _refresh_actions_list(self):
        """Rafraîchit l'affichage de la liste des actions"""
        # Vider la liste
        for item in self.actions_tree.get_children():
            self.actions_tree.delete(item)

        # Ajouter les actions
        for action in self.actions:
            icon = self._get_action_icon(action.action_type)
            self.actions_tree.insert('', 'end', text=f"{icon} {action.name}",
                                    values=(action.name,), tags=(action.action_type,))

    def _get_action_icon(self, action_type: str) -> str:
        """Retourne une icône pour le type d'action"""
        icons = {
            'carte': '🗺️',
            'collage': '🖼️',
            'titreJour': '📅'
        }
        return icons.get(action_type, '❓')

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

            # Créer la nouvelle action
            action = ActionConfig(type_var.get(), name)
            self.actions.append(action)
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
        self._refresh_actions_list()
        self.current_action = None
        self._show_detail_panel(None)

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
        self.detail_title.config(text=f"{self._get_action_icon(action.action_type)} {action.name}")

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
                'date': self.collage_date_var.get(),
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
        self.collage_date_var.set(params.get('date', ''))

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
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les images",
            initialdir=self.target_folder_var.get(),
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

    def _add_titre_jour_images(self):
        """Ajoute des images au titre du jour"""
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les images",
            initialdir=self.target_folder_var.get(),
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

    # ========== Parcourir les fichiers ==========

    def _browse_target_folder(self):
        """Ouvre un dialogue pour sélectionner le dossier cible"""
        folder = filedialog.askdirectory(
            title="Sélectionner le dossier cible",
            initialdir=self.target_folder_var.get()
        )
        if folder:
            self.target_folder_var.set(folder)
            self.config_manager.set_target_folder(folder)

    def _browse_gpx_file(self):
        """Ouvre un dialogue pour sélectionner le fichier GPX"""
        filename = filedialog.askopenfilename(
            title="Sélectionner le fichier GPX",
            initialdir=self.target_folder_var.get(),
            filetypes=[("Fichiers GPX", "*.gpx"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.carte_gpx_var.set(filename)

    def _browse_ref_image(self):
        """Ouvre un dialogue pour sélectionner l'image de référence"""
        filename = filedialog.askopenfilename(
            title="Sélectionner l'image de référence",
            initialdir=self.target_folder_var.get(),
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.carte_ref_image_var.set(filename)

    # ========== Génération ==========

    def _generate_image(self):
        """Génère l'image pour l'action sélectionnée"""
        if self.current_action is None:
            messagebox.showwarning("Attention", "Veuillez sélectionner une action")
            return

        # Sauvegarder les paramètres actuels
        self._save_current_action()

        # Lancer la génération selon le type
        if self.current_action.action_type == 'carte':
            self._generate_carte()
        elif self.current_action.action_type == 'collage':
            self._generate_collage()
        elif self.current_action.action_type == 'titreJour':
            self._generate_titre_jour()

    def _generate_carte(self):
        """Génère une carte"""
        params = self.current_action.params

        # Vérifier les champs obligatoires
        if not params.get('gpx_file'):
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier GPX")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_carte_thread)
        thread.start()

    def _generate_carte_thread(self):
        """Génère la carte (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération de la carte '{self.current_action.name}'...")

            params = self.current_action.params

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

            # Changer vers le dossier cible
            target_folder = self.target_folder_var.get()
            if target_folder:
                os.chdir(target_folder)

            # Générer la carte
            generate_map(
                gpx_file, start_time, end_time, city_list,
                self.current_action.name, ref_image, marge, titre,
                log_callback=self._log
            )

            self._log("✅ Génération terminée avec succès !")

        except Exception as e:
            self._log(f"❌ Erreur : {str(e)}")
            messagebox.showerror("Erreur", f"Erreur lors de la génération : {str(e)}")

    def _generate_collage(self):
        """Génère un collage"""
        params = self.current_action.params
        images = params.get('images', [])

        # Vérifier qu'il y a des images
        if len(images) < 2:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins 2 images")
            return
        if len(images) > 7:
            messagebox.showerror("Erreur", "Maximum 7 images autorisées")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_collage_thread)
        thread.start()

    def _generate_collage_thread(self):
        """Génère le collage (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération du collage '{self.current_action.name}'...")

            params = self.current_action.params

            # Récupérer les paramètres
            title = params.get('title') or None
            date_str = params.get('date') or None
            images = params.get('images', [])

            # Changer vers le dossier cible
            target_folder = self.target_folder_var.get()
            if target_folder:
                os.chdir(target_folder)

            # Générer le collage
            output_file = generate_collage(
                images,
                title=title,
                date_str=date_str,
                output_name=self.current_action.name,
                log_callback=self._log
            )

            self._log(f"✅ Collage généré : {output_file}")

        except Exception as e:
            self._log(f"❌ Erreur : {str(e)}")
            messagebox.showerror("Erreur", f"Erreur lors de la génération : {str(e)}")

    def _generate_titre_jour(self):
        """Génère un titre du jour"""
        params = self.current_action.params
        images = params.get('images', [])

        # Vérifier les champs obligatoires
        if not params.get('title'):
            messagebox.showerror("Erreur", "Veuillez saisir un titre")
            return
        if not params.get('date'):
            messagebox.showerror("Erreur", "Veuillez saisir une date")
            return
        if len(images) < 2:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins 2 images")
            return
        if len(images) > 7:
            messagebox.showerror("Erreur", "Maximum 7 images autorisées")
            return

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_titre_jour_thread)
        thread.start()

    def _generate_titre_jour_thread(self):
        """Génère le titre du jour (exécuté dans un thread)"""
        try:
            self._log(f"🚀 Génération du titre du jour '{self.current_action.name}'...")

            params = self.current_action.params

            # Récupérer les paramètres
            title = params.get('title')
            date_str = params.get('date')
            images = params.get('images', [])

            # Valider le format de date
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Le format de date doit être YYYY-MM-DD")

            # Changer vers le dossier cible
            target_folder = self.target_folder_var.get()
            if target_folder:
                os.chdir(target_folder)

            # Générer le titre du jour
            output_file = generate_titre_jour(
                images,
                date_str=date_str,
                title=title,
                output_name=self.current_action.name,
                log_callback=self._log
            )

            self._log(f"✅ Titre du jour généré : {output_file}")

        except Exception as e:
            self._log(f"❌ Erreur : {str(e)}")
            messagebox.showerror("Erreur", f"Erreur lors de la génération : {str(e)}")

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
        self.target_folder_var.set(self.config_manager.get_target_folder())

    def _on_closing(self):
        """Gère la fermeture de l'application"""
        # Sauvegarder la configuration actuelle
        self._save_current_action()

        # Sauvegarder la géométrie de la fenêtre
        self.config_manager.set("window_geometry", self.root.geometry())

        self.root.destroy()


def main():
    """Point d'entrée principal de l'application"""
    root = tk.Tk()
    app = PhotosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
