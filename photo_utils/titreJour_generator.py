"""
Module de génération de collages "Titre du Jour"
Extrait et adapté depuis GenererTitreJour.py
"""
import os
import random
import piexif
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS


def log(msg, callback=None):
    """Affiche un message de log"""
    message = f"➡ {msg}"
    if callback:
        callback(message)
    else:
        print(message)


def get_photo_date(img_path):
    """Récupère la date de prise de vue d'une image via EXIF"""
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name in ["DateTimeOriginal", "DateTime"]:
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except (AttributeError, KeyError, ValueError):
        pass

    # Fallback : date de modification du fichier
    return datetime.fromtimestamp(os.path.getmtime(img_path))


def generate_titre_jour(image_paths, date_str, title, output_name=None, log_callback=None):
    """
    Génère un collage "Titre du Jour" à partir d'une liste d'images

    Args:
        image_paths: Liste des chemins des images (2 à 7 images)
        date_str: Date à afficher au format YYYY-MM-DD
        title: Titre à afficher
        output_name: Nom du fichier de sortie sans extension (optionnel, utilise date_str par défaut)
        log_callback: Fonction de callback pour les logs (optionnel)

    Returns:
        Le chemin du fichier généré
    """
    if len(image_paths) < 2 or len(image_paths) > 7:
        raise ValueError("Veuillez fournir entre 2 et 7 images.")

    # Vérifier que les images existent
    for path in image_paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Fichier non trouvé : {path}")

    # Déterminer le nom de fichier de sortie
    if output_name:
        output = f"{output_name}.jpg"
    else:
        output = f"{date_str}.jpg"

    log(f"🎨 Génération du titre du jour avec {len(image_paths)} images", log_callback)
    log(f"   Titre : {title}", log_callback)
    log(f"   Date : {date_str}", log_callback)

    # Dimensions 4K
    W, H = 3840, 2160
    background_color = (0, 0, 0)  # fond noir
    border_size = 20

    # Créer la toile (fond noir)
    canvas = Image.new("RGB", (W, H), background_color)
    draw = ImageDraw.Draw(canvas)

    # Charger une police
    try:
        font_title = ImageFont.truetype("arial.ttf", 120)
        font_date = ImageFont.truetype("arial.ttf", 80)
    except:
        font_title = ImageFont.load_default()
        font_date = ImageFont.load_default()

    # Écrire le titre et la date en blanc
    margin = 30
    header_height = 250
    draw.text((margin, margin), title, font=font_title, fill="white")
    draw.text((margin, margin + 140), date_str, font=font_date, fill="white")

    # Zone pour les photos (plus grande)
    photo_area = (margin, header_height, W - margin, H - margin)
    x_min, y_min, x_max, y_max = photo_area

    # Layouts adaptatifs selon le nombre de photos
    num_photos = len(image_paths)

    if num_photos == 2:
        positions = [(0, 0), (1, 0)]
        grid_cols, grid_rows = 2, 1
    elif num_photos == 3:
        positions = [(0, 0), (1, 0), (0.5, 1)]
        grid_cols, grid_rows = 2, 2
    elif num_photos == 4:
        positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
        grid_cols, grid_rows = 2, 2
    elif num_photos == 5:
        positions = [(0, 0), (1, 0), (2, 0), (0.5, 1), (1.5, 1)]
        grid_cols, grid_rows = 3, 2
    elif num_photos == 6:
        positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]
        grid_cols, grid_rows = 3, 2
    else:  # 7 photos
        positions = [(0, 0.5), (0, 2), (1, 0.5), (1, 2), (2, 0), (2, 1), (2, 2)]
        grid_cols, grid_rows = 3, 3

    # Calculer les dimensions des cellules
    cell_w = (x_max - x_min) / grid_cols
    cell_h = (y_max - y_min) / grid_rows

    # Mélanger aléatoirement l'ordre des positions
    shuffled_positions = positions.copy()
    random.shuffle(shuffled_positions)

    # Placer les images
    for idx, img_path in enumerate(image_paths):
        log(f"  → Ajout de l'image {idx + 1}/{num_photos}", log_callback)
        img = Image.open(img_path)

        # Lire et appliquer l'orientation EXIF
        try:
            exif_data = img._getexif()
            if exif_data is not None:
                orientation = exif_data.get(274)  # Tag 274 = Orientation
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            pass

        img = img.convert("RGBA")

        # Taille : facteur de 1.3 (fixe, pas aléatoire)
        size_factor = 1.3
        max_w, max_h = int((x_max - x_min) / 3 * size_factor), int((y_max - y_min) / 3 * size_factor)
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

        # Bordure blanche
        bordered = Image.new("RGBA", (img.width + 2*border_size, img.height + 2*border_size), (0, 0, 0, 0))
        ImageDraw.Draw(bordered).rectangle(
            [(0, 0), (bordered.width-1, bordered.height-1)],
            fill=(255, 255, 255, 255)
        )
        bordered.paste(img, (border_size, border_size), img)

        # Rotation aléatoire légère
        angle = random.randint(-15, 15)
        rotated = bordered.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

        # Utiliser la position prédéfinie mélangée
        cx, cy = shuffled_positions[idx]

        # Calculer le centre de la cellule avec désalignement (variation de 15%)
        alea = 0.15
        center_x = x_min + cx * cell_w + cell_w / 2 + random.uniform(-cell_w * alea, cell_w * alea)
        center_y = y_min + cy * cell_h + cell_h / 2 + random.uniform(-cell_h * alea, cell_h * alea)

        # Ajouter un décalage aléatoire supplémentaire pour plus de naturel
        alea2 = 40
        offset_x = random.randint(-alea2, alea2)
        offset_y = random.randint(-alea2, alea2)

        # Position finale (centrée avec décalage)
        x = int(center_x - rotated.width / 2 + offset_x)
        y = int(center_y - rotated.height / 2 + offset_y)

        canvas.paste(rotated, (x, y), rotated)

    # Sauvegarde image
    canvas.save(output, "JPEG", quality=95)
    log(f"💾 Sauvegarde de l'image : {output}", log_callback)

    # Ajouter EXIF
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=2, minute=0, second=0)
        dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
        zeroth_ifd = {
            piexif.ImageIFD.Software: "Python Collage Script",
            piexif.ImageIFD.DateTime: dt_str,
            piexif.ImageIFD.ImageDescription: title.encode("utf-8"),
            piexif.ImageIFD.Rating: 5
        }
        exif_ifd = {
            piexif.ExifIFD.DateTimeOriginal: dt_str,
            piexif.ExifIFD.DateTimeDigitized: dt_str,
        }
        exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "1st": {}, "GPS": {}}
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, output)
        log("✅ Titre du jour généré avec succès", log_callback)
        log(f"   Date EXIF : {dt_str}", log_callback)
        log(f"   Rating : ⭐⭐⭐⭐⭐", log_callback)
    except Exception as e:
        log(f"⚠ Impossible de modifier les EXIF : {e}", log_callback)

    return output
