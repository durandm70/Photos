#!/usr/bin/env python3
"""
Application GUI unifiée pour la gestion de photos
Intègre les fonctionnalités de génération de cartes et de collages
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import threading

# Import des modules locaux
from photo_utils import ConfigManager, generate_map, parse_ville, generate_collage


class PhotosApp:
    """Application principale pour la gestion de photos"""

    def __init__(self, root):
        """Initialise l'application"""
        self.root = root
        self.root.title("Photos Manager - Application Unifiée")

        # Gestionnaire de configuration
        self.config = ConfigManager()

        # Restaurer la géométrie de la fenêtre
        geometry = self.config.get("window_geometry", "1000x750")
        self.root.geometry(geometry)

        # Créer l'interface
        self._create_widgets()

        # Charger les paramètres sauvegardés
        self._load_settings()

        # Sauvegarder la géométrie en quittant
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        """Crée les widgets de l'interface"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configuration du redimensionnement
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Section dossier cible (commune à toutes les opérations)
        self._create_target_folder_section(main_frame)

        # Notebook pour les différentes opérations
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        # Onglet 1 : Génération de carte
        self._create_map_tab()

        # Onglet 2 : Génération de collage
        self._create_collage_tab()

    def _create_target_folder_section(self, parent):
        """Crée la section de sélection du dossier cible"""
        folder_frame = ttk.LabelFrame(parent, text="Dossier cible", padding="10")
        folder_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        folder_frame.columnconfigure(1, weight=1)

        ttk.Label(folder_frame, text="Dossier :").grid(row=0, column=0, sticky=tk.W)

        self.target_folder_var = tk.StringVar()
        folder_entry = ttk.Entry(folder_frame, textvariable=self.target_folder_var)
        folder_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))

        browse_btn = ttk.Button(folder_frame, text="...", width=5,
                                command=self._browse_target_folder)
        browse_btn.grid(row=0, column=2, sticky=tk.E)

    def _create_map_tab(self):
        """Crée l'onglet de génération de carte"""
        map_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(map_frame, text="Générer une carte")

        # Configuration du redimensionnement
        map_frame.columnconfigure(1, weight=1)
        map_frame.rowconfigure(10, weight=1)

        # Fichier GPX
        row = 0
        ttk.Label(map_frame, text="Fichier GPX :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.gpx_file_var = tk.StringVar()
        gpx_entry = ttk.Entry(map_frame, textvariable=self.gpx_file_var)
        gpx_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(map_frame, text="...", width=5,
                   command=self._browse_gpx_file).grid(row=row, column=2)

        # Nom de sortie
        row += 1
        ttk.Label(map_frame, text="Nom de sortie :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_output_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_output_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Titre
        row += 1
        ttk.Label(map_frame, text="Titre (optionnel) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_title_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_title_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Date
        row += 1
        ttk.Label(map_frame, text="Date (YYYY-MM-DD) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_date_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_date_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(map_frame, text="(optionnel, laissez vide pour tout le GPX)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Plage horaire
        row += 2
        ttk.Label(map_frame, text="Plage horaire :").grid(row=row, column=0, sticky=tk.W, pady=2)
        time_frame = ttk.Frame(map_frame)
        time_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(time_frame, text="Début :").pack(side=tk.LEFT)
        self.map_start_time_var = tk.StringVar()
        ttk.Entry(time_frame, textvariable=self.map_start_time_var, width=20).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Label(time_frame, text="Fin :").pack(side=tk.LEFT)
        self.map_end_time_var = tk.StringVar()
        ttk.Entry(time_frame, textvariable=self.map_end_time_var, width=20).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(map_frame, text="(format: HH:MM:SS, optionnel)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Villes
        row += 2
        ttk.Label(map_frame, text="Villes :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_cities_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_cities_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(map_frame, text="(séparées par des virgules, format: ville ou ville:nom:position)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Marge
        row += 2
        ttk.Label(map_frame, text="Marge (mètres) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_margin_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_margin_var, width=15).grid(
            row=row, column=1, sticky=tk.W, padx=(5, 5))
        ttk.Label(map_frame, text="(optionnel, auto si vide)",
                  font=('TkDefaultFont', 8)).grid(row=row, column=2, sticky=tk.W)

        # Image de référence
        row += 1
        ttk.Label(map_frame, text="Image de référence :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.map_ref_image_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.map_ref_image_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(map_frame, text="...", width=5,
                   command=self._browse_ref_image).grid(row=row, column=2)

        # Bouton de génération
        row += 1
        ttk.Button(map_frame, text="Générer la carte", command=self._generate_map).grid(
            row=row, column=0, columnspan=3, pady=(10, 5))

        # Zone de log
        row += 1
        ttk.Label(map_frame, text="Logs :").grid(row=row, column=0, sticky=tk.W, pady=(5, 2))
        self.map_log_text = scrolledtext.ScrolledText(map_frame, height=10, width=80)
        self.map_log_text.grid(row=row+1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

    def _create_collage_tab(self):
        """Crée l'onglet de génération de collage"""
        collage_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(collage_frame, text="Générer un collage")

        # Configuration du redimensionnement
        collage_frame.columnconfigure(1, weight=1)
        collage_frame.rowconfigure(10, weight=1)

        # Titre
        row = 0
        ttk.Label(collage_frame, text="Titre (optionnel) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_title_var = tk.StringVar()
        ttk.Entry(collage_frame, textvariable=self.collage_title_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)

        # Date
        row += 1
        ttk.Label(collage_frame, text="Date (YYYY-MM-DD) :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_date_var = tk.StringVar()
        ttk.Entry(collage_frame, textvariable=self.collage_date_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(collage_frame, text="(optionnel, date de la photo la plus ancienne si vide)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Nom de sortie
        row += 2
        ttk.Label(collage_frame, text="Nom de sortie :").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.collage_output_var = tk.StringVar()
        ttk.Entry(collage_frame, textvariable=self.collage_output_var).grid(
            row=row, column=1, sticky=(tk.W, tk.E), padx=(5, 5), columnspan=2)
        ttk.Label(collage_frame, text="(optionnel, auto si vide)",
                  font=('TkDefaultFont', 8)).grid(row=row+1, column=1, sticky=tk.W, padx=(5, 0))

        # Sélection des images
        row += 2
        ttk.Label(collage_frame, text="Images sélectionnées :").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Button(collage_frame, text="Ajouter des images", command=self._add_collage_images).grid(
            row=row, column=1, sticky=tk.W, padx=(5, 5))
        ttk.Button(collage_frame, text="Effacer la sélection", command=self._clear_collage_images).grid(
            row=row, column=2, sticky=tk.W)

        # Liste des images
        row += 1
        list_frame = ttk.Frame(collage_frame)
        list_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.collage_images_listbox = tk.Listbox(list_frame, height=10)
        self.collage_images_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.collage_images_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.collage_images_listbox.configure(yscrollcommand=scrollbar.set)

        self.collage_images = []

        # Bouton de génération
        row += 1
        ttk.Button(collage_frame, text="Générer le collage", command=self._generate_collage).grid(
            row=row, column=0, columnspan=3, pady=(10, 5))

        # Zone de log
        row += 1
        ttk.Label(collage_frame, text="Logs :").grid(row=row, column=0, sticky=tk.W, pady=(5, 2))
        self.collage_log_text = scrolledtext.ScrolledText(collage_frame, height=10, width=80)
        self.collage_log_text.grid(row=row+1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

    def _browse_target_folder(self):
        """Ouvre un dialogue pour sélectionner le dossier cible"""
        folder = filedialog.askdirectory(
            title="Sélectionner le dossier cible",
            initialdir=self.target_folder_var.get()
        )
        if folder:
            self.target_folder_var.set(folder)
            self.config.set_target_folder(folder)

    def _browse_gpx_file(self):
        """Ouvre un dialogue pour sélectionner le fichier GPX"""
        filename = filedialog.askopenfilename(
            title="Sélectionner le fichier GPX",
            initialdir=self.target_folder_var.get(),
            filetypes=[("Fichiers GPX", "*.gpx"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.gpx_file_var.set(filename)

    def _browse_ref_image(self):
        """Ouvre un dialogue pour sélectionner l'image de référence"""
        filename = filedialog.askopenfilename(
            title="Sélectionner l'image de référence",
            initialdir=self.target_folder_var.get(),
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )
        if filename:
            self.map_ref_image_var.set(filename)

    def _add_collage_images(self):
        """Ajoute des images à la liste du collage"""
        filenames = filedialog.askopenfilenames(
            title="Sélectionner les images",
            initialdir=self.target_folder_var.get(),
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("Tous les fichiers", "*.*")]
        )
        for filename in filenames:
            if filename not in self.collage_images:
                self.collage_images.append(filename)
                self.collage_images_listbox.insert(tk.END, os.path.basename(filename))

    def _clear_collage_images(self):
        """Efface la sélection d'images du collage"""
        self.collage_images = []
        self.collage_images_listbox.delete(0, tk.END)

    def _log_map(self, message):
        """Ajoute un message au log de la carte"""
        self.map_log_text.insert(tk.END, message + "\n")
        self.map_log_text.see(tk.END)
        self.root.update_idletasks()

    def _log_collage(self, message):
        """Ajoute un message au log du collage"""
        self.collage_log_text.insert(tk.END, message + "\n")
        self.collage_log_text.see(tk.END)
        self.root.update_idletasks()

    def _generate_map(self):
        """Lance la génération de la carte dans un thread séparé"""
        # Vérifier les champs obligatoires
        if not self.gpx_file_var.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier GPX")
            return
        if not self.map_output_var.get():
            messagebox.showerror("Erreur", "Veuillez saisir un nom de sortie")
            return

        # Désactiver le bouton pendant la génération
        for widget in self.notebook.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state='disabled')

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_map_thread)
        thread.start()

    def _generate_map_thread(self):
        """Génère la carte (exécuté dans un thread)"""
        try:
            self._log_map("🚀 Démarrage de la génération de la carte...")

            # Récupérer les paramètres
            gpx_file = self.gpx_file_var.get()
            output_name = self.map_output_var.get()
            titre = self.map_title_var.get() or None
            date_str = self.map_date_var.get()
            start_time_str = self.map_start_time_var.get()
            end_time_str = self.map_end_time_var.get()
            cities_str = self.map_cities_var.get()
            margin_str = self.map_margin_var.get()
            ref_image = self.map_ref_image_var.get() or None

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
                    self._log_map("⚠ Marge invalide, utilisation de la valeur automatique")

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
                    self._log_map(f"⚠ Erreur de format de date : {e}")
                    raise

            # Changer vers le dossier cible
            target_folder = self.target_folder_var.get()
            if target_folder:
                os.chdir(target_folder)

            # Générer la carte
            generate_map(
                gpx_file, start_time, end_time, city_list,
                output_name, ref_image, marge, titre,
                log_callback=self._log_map
            )

            self._log_map("✅ Génération terminée avec succès !")

        except Exception as e:
            self._log_map(f"❌ Erreur : {str(e)}")
            messagebox.showerror("Erreur", f"Erreur lors de la génération : {str(e)}")

        finally:
            # Réactiver les boutons
            for widget in self.notebook.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.configure(state='normal')

    def _generate_collage(self):
        """Lance la génération du collage dans un thread séparé"""
        # Vérifier qu'il y a des images
        if len(self.collage_images) < 2:
            messagebox.showerror("Erreur", "Veuillez sélectionner au moins 2 images")
            return
        if len(self.collage_images) > 7:
            messagebox.showerror("Erreur", "Maximum 7 images autorisées")
            return

        # Désactiver le bouton pendant la génération
        for widget in self.notebook.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state='disabled')

        # Lancer la génération dans un thread
        thread = threading.Thread(target=self._generate_collage_thread)
        thread.start()

    def _generate_collage_thread(self):
        """Génère le collage (exécuté dans un thread)"""
        try:
            self._log_collage("🚀 Démarrage de la génération du collage...")

            # Récupérer les paramètres
            title = self.collage_title_var.get() or None
            date_str = self.collage_date_var.get() or None
            output_name = self.collage_output_var.get() or None

            # Changer vers le dossier cible
            target_folder = self.target_folder_var.get()
            if target_folder:
                os.chdir(target_folder)

            # Générer le collage
            output_file = generate_collage(
                self.collage_images,
                title=title,
                date_str=date_str,
                output_name=output_name,
                log_callback=self._log_collage
            )

            self._log_collage(f"✅ Collage généré : {output_file}")

        except Exception as e:
            self._log_collage(f"❌ Erreur : {str(e)}")
            messagebox.showerror("Erreur", f"Erreur lors de la génération : {str(e)}")

        finally:
            # Réactiver les boutons
            for widget in self.notebook.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button):
                        child.configure(state='normal')

    def _load_settings(self):
        """Charge les paramètres sauvegardés"""
        self.target_folder_var.set(self.config.get_target_folder())

    def _on_closing(self):
        """Gère la fermeture de l'application"""
        # Sauvegarder la géométrie de la fenêtre
        self.config.set("window_geometry", self.root.geometry())
        self.root.destroy()


def main():
    """Point d'entrée principal de l'application"""
    root = tk.Tk()
    app = PhotosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
