"""
Package photo_utils - Utilitaires pour la gestion de photos
Contient les modules pour la génération de cartes et de collages
"""

from .config_manager import ConfigManager
from .map_generator import generate_map, parse_ville
from .collage_generator import generate_collage

__all__ = [
    'ConfigManager',
    'generate_map',
    'parse_ville',
    'generate_collage'
]
