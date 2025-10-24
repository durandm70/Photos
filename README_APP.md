# Application Photos Manager

Application GUI unifiée pour la gestion de photos avec génération de cartes et collages.

## Fonctionnalités

### 1. Génération de cartes depuis GPX
- Création de cartes à partir de fichiers GPX
- Filtrage par date et plage horaire
- Ajout de villes avec géocodage automatique
- Personnalisation du titre et des marges
- Application de métadonnées EXIF

### 2. Génération de collages photos
- Création de collages avec 2 à 7 photos
- Disposition aléatoire et artistique
- Rotation légère des photos pour un effet naturel
- Titre optionnel
- Métadonnées EXIF avec notation 5 étoiles

## Installation

### Prérequis
- Python 3.9 ou supérieur
- pip (gestionnaire de paquets Python)

### Installation des dépendances

```bash
pip install -r requirements.txt
```

## Utilisation

### Lancement de l'application

```bash
python app.py
```

ou

```bash
python3 app.py
```

### Configuration du dossier cible

1. Au démarrage, sélectionnez le dossier cible où seront générés les fichiers
2. Ce dossier sera mémorisé pour les prochaines utilisations
3. Utilisez le bouton "..." pour parcourir et sélectionner un nouveau dossier

### Génération d'une carte

1. Allez dans l'onglet "Générer une carte"
2. Sélectionnez un fichier GPX
3. Saisissez un nom de sortie (sans extension, .jpg sera ajouté)
4. (Optionnel) Ajoutez un titre pour la carte
5. (Optionnel) Filtrez par date (format: YYYY-MM-DD)
6. (Optionnel) Précisez une plage horaire (format: HH:MM:SS)
7. (Optionnel) Ajoutez des villes (séparées par des virgules)
   - Format simple: `Paris, Lyon, Marseille`
   - Avec nom personnalisé: `Paris:Ville Lumière, Lyon:Capital des Gaules`
   - Avec position: `Paris:Paris:NE, Lyon:Lyon:SO`
   - Positions possibles: N, S, E, O, NE, NO, SE, SO
8. (Optionnel) Définissez une marge en mètres
9. (Optionnel) Sélectionnez une image de référence pour les métadonnées EXIF
10. Cliquez sur "Générer la carte"

### Génération d'un collage

1. Allez dans l'onglet "Générer un collage"
2. (Optionnel) Saisissez un titre
3. (Optionnel) Saisissez un nom de sortie
4. Cliquez sur "Ajouter des images" et sélectionnez 2 à 7 photos
5. Cliquez sur "Générer le collage"

## Architecture du code

L'application est structurée en modules pour faciliter la maintenance :

- `app.py` : Interface graphique principale (tkinter)
- `config_manager.py` : Gestion de la persistance des paramètres
- `map_generator.py` : Logique de génération de cartes depuis GPX
- `collage_generator.py` : Logique de génération de collages photos

## Configuration

Les paramètres utilisateur sont automatiquement sauvegardés dans :
- Linux/Mac : `~/.photos_app/config.json`
- Windows : `%USERPROFILE%\.photos_app\config.json`

Les paramètres sauvegardés incluent :
- Dossier cible
- Géométrie de la fenêtre

## Cache

Les fonds de carte téléchargés sont mis en cache dans le dossier `__cache` pour accélérer les générations futures.

## Dépannage

### Erreur de police "ARLRDBD.TTF"
Si la police Bradley Hand n'est pas trouvée, l'application utilisera la police par défaut. Cela n'affecte pas la génération, juste le style du texte.

### Erreur de géocodage
Le géocodage des villes utilise OpenStreetMap Nominatim. En cas d'échec :
- Vérifiez votre connexion internet
- Attendez quelques secondes avant de réessayer (limite de taux)
- Vérifiez l'orthographe des noms de villes

### Erreur EXIF
Si les métadonnées EXIF ne peuvent pas être appliquées, le fichier sera quand même généré sans ces métadonnées.

## Licence

Ce projet est dérivé des scripts originaux `GenererCarte.py` et `collage.py`.
