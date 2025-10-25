# Photos Manager

Application GUI unifiée pour la gestion de photos avec génération de cartes et collages.

## Fonctionnalités principales

- **Génération de cartes depuis fichiers GPX** : Créez des cartes visuelles à partir de vos traces GPS
- **Génération de collages photos** : Créez des collages artistiques avec 2 à 7 photos
- **Interface graphique intuitive** : Application tkinter facile à utiliser
- **Gestion des métadonnées EXIF** : Application automatique de dates et notations

## Installation rapide

1. **Clonez le dépôt** (ou téléchargez le code)

2. **Installez les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

3. **Lancez l'application** :
   ```bash
   python app.py
   ```

## Documentation complète

Pour plus de détails sur l'utilisation, la configuration et le dépannage, consultez [README_APP.md](README_APP.md).

## Dépannage rapide

Si vous obtenez une erreur `ModuleNotFoundError: No module named 'matplotlib'` (ou autre module), vous devez installer les dépendances :

```bash
pip install -r requirements.txt
```

Sur Windows, vous devrez peut-être utiliser :
```bash
python -m pip install -r requirements.txt
```

## Prérequis

- Python 3.9 ou supérieur
- pip (gestionnaire de paquets Python)

## Licence

Ce projet est dérivé des scripts originaux `GenererCarte.py` et `collage.py`.