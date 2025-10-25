"""
Gestionnaire de configuration pour l'application Photos
Permet de sauvegarder et charger les paramètres utilisateur
"""
import json
import os
from pathlib import Path


class ConfigManager:
    """Gère la persistance des paramètres de l'application"""

    def __init__(self, config_file=None):
        """
        Initialise le gestionnaire de configuration

        Args:
            config_file: Chemin du fichier de configuration (optionnel)
        """
        if config_file is None:
            # Utiliser le dossier home de l'utilisateur
            config_dir = Path.home() / ".photos_app"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "config.json"

        self.config_file = Path(config_file)
        self.settings = self._load_settings()

    def _load_settings(self):
        """Charge les paramètres depuis le fichier de configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._default_settings()
        return self._default_settings()

    def _default_settings(self):
        """Retourne les paramètres par défaut"""
        return {
            "target_folder": os.getcwd(),
            "last_gpx_file": "",
            "last_output_name": "",
            "last_cities": "",
            "last_title": "",
            "last_margin": "",
            "window_geometry": "900x700"
        }

    def save_settings(self):
        """Sauvegarde les paramètres dans le fichier de configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Erreur lors de la sauvegarde des paramètres : {e}")

    def get(self, key, default=None):
        """
        Récupère une valeur de configuration

        Args:
            key: Clé du paramètre
            default: Valeur par défaut si la clé n'existe pas

        Returns:
            La valeur du paramètre ou la valeur par défaut
        """
        return self.settings.get(key, default)

    def set(self, key, value):
        """
        Définit une valeur de configuration

        Args:
            key: Clé du paramètre
            value: Valeur du paramètre
        """
        self.settings[key] = value
        self.save_settings()

    def get_target_folder(self):
        """Récupère le dossier cible"""
        return self.get("target_folder", os.getcwd())

    def set_target_folder(self, folder):
        """Définit le dossier cible"""
        self.set("target_folder", folder)
