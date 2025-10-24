import sys
import os
import random
import piexif
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from PIL.ExifTags import TAGS

def get_photo_date(img_path):
    """Récupère la date de prise de vue d'une image via EXIF."""
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        if exif_data:
            # Chercher DateTimeOriginal ou DateTime
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name in ["DateTimeOriginal", "DateTime"]:
                    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except (AttributeError, KeyError, ValueError):
        pass
    
    # Fallback : utiliser la date de modification du fichier
    return datetime.fromtimestamp(os.path.getmtime(img_path))

def generate_collage(image_paths, title=None):
    """Génère un collage à partir d'une liste d'images."""
    
    # Récupérer la date la plus tôt de toutes les photos
    photo_dates = [get_photo_date(path) for path in image_paths]
    first_photo_date = min(photo_dates)
    date_str = first_photo_date.strftime("%Y-%m-%d")
    
    # Utiliser le titre fourni ou générer le nom par défaut
    if title:
        output = f"{title}.jpg"
    else:
        output = f"collage_{date_str}.jpg"
    
    # Dimensions 4K
    W, H = 3840, 2160
    background_color = (0, 0, 0)
    border_size = 20
    
    # Créer la toile
    canvas = Image.new("RGB", (W, H), background_color)
    draw = ImageDraw.Draw(canvas)
    
    # Zone pour les photos
    if title:
        # Charger la police si titre fourni
        try:
            font_title = ImageFont.truetype("arial.ttf", 120)
        except:
            font_title = ImageFont.load_default()
        
        margin = 30
        header_height = 200
        draw.text((margin, margin), title, font=font_title, fill="white")
        photo_area = (margin, header_height, W - margin, H - margin)
    else:
        margin = 30
        photo_area = (margin, margin, W - margin, H - margin)
    x_min, y_min, x_max, y_max = photo_area
    
    # Layouts adaptatifs
    num_photos = len(image_paths)
    
    if num_photos == 2:
        positions = [(0.2, 0), (1, 0)]
        grid_cols, grid_rows = 2, 1.5
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
        positions = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
        grid_cols, grid_rows = 3, 2
    else:  # 7+ photos
        positions = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (1, 2)]
        grid_cols, grid_rows = 3, 3
    
    # Redimensionner positions si nécessaire
    if num_photos < len(positions):
        positions = positions[:num_photos]
    
    # Calculer les dimensions des cellules
    cell_w = (x_max - x_min) / grid_cols
    cell_h = (y_max - y_min) / grid_rows
    
    # Mélanger aléatoirement
    shuffled_positions = positions.copy()
    random.shuffle(shuffled_positions)
    
    # Placer les images
    for idx, img_path in enumerate(image_paths):
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
        
        # Redimensionner
        max_w, max_h = int(cell_w * 0.95), int(cell_h * 0.95)
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
        
        # Position avec désalignement
        cx, cy = shuffled_positions[idx]
        center_x = x_min + cx * cell_w + cell_w / 2 + random.uniform(-cell_w * 0.4, cell_w * 0.4)
        center_y = y_min + cy * cell_h + cell_h / 2 + random.uniform(-cell_h * 0.4, cell_h * 0.4)
        
        offset_x = random.randint(-40, 40)
        offset_y = random.randint(-40, 40)
        
        x = int(center_x - rotated.width / 2 + offset_x)
        y = int(center_y - rotated.height / 2 + offset_y)
        
        # Limiter aux frontières
        x = max(x_min, min(x, x_max - rotated.width))
        y = max(y_min, min(y, y_max - rotated.height))
        
        canvas.paste(rotated, (x, y), rotated)
    
    # Sauvegarde
    canvas.save(output, "JPEG", quality=95)
    
    # Ajouter EXIF avec 5 étoiles
    try:
        dt_str = first_photo_date.strftime("%Y:%m:%d %H:%M:%S")
        zeroth_ifd = {
            piexif.ImageIFD.Software: "Collage Generator",
            piexif.ImageIFD.DateTime: dt_str,
            piexif.ImageIFD.Rating: 5  # 5 étoiles
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
        print(f"✅ Collage généré : {output}")
        print(f"   Date : {dt_str}")
        print(f"   Titre : {title}")
        print(f"   Rating : ⭐⭐⭐⭐⭐")
    except Exception as e:
        print(f"⚠ Erreur EXIF : {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python collage.py <img1> [<img2> ... <img7>] [--titre 'Titre du collage']")
        print("Exemple: python collage.py photo1.jpg photo2.jpg photo3.jpg --titre 'Vacances'")
        sys.exit(1)
    
    # Parser les arguments
    image_paths = []
    title = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--titre" and i + 1 < len(sys.argv):
            title = sys.argv[i + 1]
            i += 2
        else:
            image_paths.append(sys.argv[i])
            i += 1
    
    if len(image_paths) < 2 or len(image_paths) > 7:
        print("❌ Veuillez fournir entre 2 et 7 images.")
        sys.exit(1)
    
    # Vérifier que les images existent
    for path in image_paths:
        if not os.path.isfile(path):
            print(f"❌ Fichier non trouvé : {path}")
            sys.exit(1)
    
    generate_collage(image_paths, title)