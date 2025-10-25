"""
Module de génération de collages photos
Extrait et adapté depuis collage.py
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


def generate_collage(image_paths, title=None, date_str=None, ref_image=None, output_name=None, log_callback=None):
    """
    Génère un collage à partir d'une liste d'images

    Args:
        image_paths: Liste des chemins des images
        title: Titre à afficher (optionnel)
        date_str: Date à afficher au format YYYY-MM-DD (optionnel)
        ref_image: Chemin de l'image de référence pour la date taken (optionnel)
        output_name: Nom du fichier de sortie sans extension (optionnel)
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

    # Déterminer la date de référence pour le calcul
    if ref_image:
        # Si une image de référence est fournie, utiliser sa date
        if not os.path.isfile(ref_image):
            raise FileNotFoundError(f"Image de référence non trouvée : {ref_image}")
        reference_date = get_photo_date(ref_image)
        log(f"Utilisation de l'image de référence : {os.path.basename(ref_image)}", log_callback)
        log(f"Date de référence : {reference_date.strftime('%Y-%m-%d %H:%M:%S')}", log_callback)
    else:
        # Sinon, utiliser la date la plus tôt de toutes les photos
        photo_dates = [get_photo_date(path) for path in image_paths]
        reference_date = min(photo_dates)
        log(f"Utilisation de la photo la plus vieille comme référence", log_callback)
        log(f"Date de référence : {reference_date.strftime('%Y-%m-%d %H:%M:%S')}", log_callback)

    # Calculer la date taken finale : date de référence - 30 secondes
    from datetime import timedelta
    first_photo_date = reference_date - timedelta(seconds=30)
    log(f"Date taken du collage (référence - 30s) : {first_photo_date.strftime('%Y-%m-%d %H:%M:%S')}", log_callback)

    # Utiliser la date fournie ou celle de la photo
    if not date_str:
        date_str = first_photo_date.strftime("%Y-%m-%d")

    # Déterminer le nom de fichier de sortie
    if output_name:
        output = f"{output_name}.jpg"
    elif title:
        output = f"{title}.jpg"
    else:
        output = f"collage_{date_str}.jpg"

    log(f"🎨 Génération du collage avec {len(image_paths)} images", log_callback)

    # Dimensions 4K
    W, H = 3840, 2160
    background_color = (0, 0, 0)
    border_size = 20

    # Créer la toile
    canvas = Image.new("RGB", (W, H), background_color)
    draw = ImageDraw.Draw(canvas)

    # Zone pour les photos avec titre et date
    margin = 30
    if title:
        try:
            font_title = ImageFont.truetype("arial.ttf", 120)
            font_date = ImageFont.truetype("arial.ttf", 80)
        except:
            font_title = ImageFont.load_default()
            font_date = ImageFont.load_default()

        header_height = 250
        draw.text((margin, margin), title, font=font_title, fill="white")
        draw.text((margin, margin + 140), date_str, font=font_date, fill="white")
        photo_area = (margin, header_height, W - margin, H - margin)
    else:
        photo_area = (margin, margin, W - margin, H - margin)

    x_min, y_min, x_max, y_max = photo_area

    # Layouts adaptatifs (comme dans GenererTitreJour.py)
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

    # Mélanger aléatoirement
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
                orientation = exif_data.get(274)
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            pass

        img = img.convert("RGBA")

        # Redimensionner avec size_factor de 1.3 (comme dans GenererTitreJour.py)
        size_factor = 1.3
        max_w = int((x_max - x_min) / 3 * size_factor)
        max_h = int((y_max - y_min) / 3 * size_factor)
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

        # Bordure blanche
        bordered = Image.new("RGBA", (img.width + 2*border_size, img.height + 2*border_size), (0, 0, 0, 0))
        ImageDraw.Draw(bordered).rectangle(
            [(0, 0), (bordered.width-1, bordered.height-1)],
            fill=(255, 255, 255, 255)
        )
        bordered.paste(img, (border_size, border_size), img)

        # Rotation légère aléatoire
        angle = random.randint(-15, 15)
        rotated = bordered.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

        # Position avec désalignement (comme dans GenererTitreJour.py)
        cx, cy = shuffled_positions[idx]
        # Variation horizontale et verticale (aléa de 15%)
        alea = 0.15
        center_x = x_min + cx * cell_w + cell_w / 2 + random.uniform(-cell_w * alea, cell_w * alea)
        center_y = y_min + cy * cell_h + cell_h / 2 + random.uniform(-cell_h * alea, cell_h * alea)

        # Décalage aléatoire supplémentaire
        alea2 = 40
        offset_x = random.randint(-alea2, alea2)
        offset_y = random.randint(-alea2, alea2)

        x = int(center_x - rotated.width / 2 + offset_x)
        y = int(center_y - rotated.height / 2 + offset_y)

        canvas.paste(rotated, (x, y), rotated)

    # Sauvegarde
    canvas.save(output, "JPEG", quality=95)
    log(f"💾 Sauvegarde de l'image : {output}", log_callback)

    # Ajouter EXIF avec 5 étoiles et la date/heure calculée (référence - 30s)
    try:
        # Utiliser la date calculée (first_photo_date qui contient déjà référence - 30s)
        dt = first_photo_date
        dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")

        zeroth_ifd = {
            piexif.ImageIFD.Software: "Python Collage Script",
            piexif.ImageIFD.DateTime: dt_str,
            piexif.ImageIFD.Rating: 5
        }
        if title:
            zeroth_ifd[piexif.ImageIFD.ImageDescription] = title.encode("utf-8")
        exif_ifd = {
            piexif.ExifIFD.DateTimeOriginal: dt_str,
            piexif.ExifIFD.DateTimeDigitized: dt_str,
        }
        exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "1st": {}, "GPS": {}}
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, output)
        log("✅ Collage généré avec succès", log_callback)
        log(f"   Date : {dt_str}", log_callback)
        log(f"   Rating : ⭐⭐⭐⭐⭐", log_callback)
    except Exception as e:
        log(f"⚠ Erreur EXIF : {e}", log_callback)

    return output
