import sys
import argparse
import gpxpy
import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import contextily as ctx
from shapely.geometry import LineString, Point
import geopandas as gpd
from PIL import Image
from io import BytesIO
import os, hashlib, pickle
import matplotlib.font_manager as fm
import piexif
import requests
import numpy as np
from matplotlib.patches import FancyArrowPatch, Polygon

CACHE_DIR = "__cache"


def log(msg):
    print(f"➡ {msg}")

try:
    bradley_path = r"C:\\Windows\\Fonts\\ARLRDBD.TTF"
    bradley_prop = fm.FontProperties(fname=bradley_path, weight="bold")
except:
    log("⚠ Impossible de trouver ARLRDBD.TTF, utilisation par défaut")
    bradley_prop = None

def calculate_zoom_for_extent(xmin, ymin, xmax, ymax, width_px, height_px):
    lon_length = xmax - xmin
    lat_length = ymax - ymin
    zoom_lon = np.log2(156543.03 * width_px / lon_length)
    zoom_lat = np.log2(156543.03 * height_px / lat_length)
    zoom = int(min(zoom_lon, zoom_lat))
    return max(0, min(zoom, 18))

def adjust_bounds_to_ratio(xmin, ymin, xmax, ymax, target_ratio=4/3):
    """
    Ajuste les bounds pour respecter un ratio largeur/hauteur donné.
    Le trajet reste centré en étendant la dimension la plus petite proportionnellement.

    Args:
        xmin, ymin, xmax, ymax: Bounds actuels (EPSG:3857)
        target_ratio: Ratio cible largeur/hauteur (par défaut 4:3)

    Returns:
        xmin, ymin, xmax, ymax: Bounds ajustés
    """
    current_width = xmax - xmin
    current_height = ymax - ymin
    current_ratio = current_width / current_height

    # Calculer le centre
    center_x = (xmin + xmax) / 2
    center_y = (ymin + ymax) / 2

    if current_ratio > target_ratio:
        # La largeur est trop grande par rapport à la hauteur
        # Il faut augmenter la hauteur
        new_height = current_width / target_ratio
        ymin = center_y - new_height / 2
        ymax = center_y + new_height / 2
    elif current_ratio < target_ratio:
        # La hauteur est trop grande par rapport à la largeur
        # Il faut augmenter la largeur
        new_width = current_height * target_ratio
        xmin = center_x - new_width / 2
        xmax = center_x + new_width / 2

    log(f"📐 Ajustement au ratio {target_ratio:.2f} : {current_width:.0f}x{current_height:.0f}m → {xmax-xmin:.0f}x{ymax-ymin:.0f}m")

    return xmin, ymin, xmax, ymax

def parse_position(position_str):
    """Parse une chaîne de position (N, S, E, O, NE, NO, SE, SO) et retourne (ha, va, offset_mult)"""
    if not position_str:
        return None  # Aucune position forcée, utiliser le calcul automatique
    
    position_str = position_str.upper()
    
    # Déterminer alignement vertical
    va = "center"
    vert_offset = 0
    if 'N' in position_str:
        va = "bottom"
        vert_offset = 1
    elif 'S' in position_str:
        va = "top"
        vert_offset = -1
    
    # Déterminer alignement horizontal
    ha = "center"
    horiz_offset = 0
    if 'E' in position_str:
        ha = "left"
        horiz_offset = 1
    elif 'O' in position_str:
        ha = "right"
        horiz_offset = -1
    
    return (ha, va, horiz_offset, vert_offset)

def adjust_text_position(city_x, city_y, xmin, xmax, ymin, ymax, ax, name, forced_position=None):
    if forced_position:
        ha, va, horiz_offset, vert_offset = forced_position
    else:
        # Calcul automatique comme avant
        mid_x, mid_y = (xmin + xmax) / 2, (ymin + ymax) / 2
        ha = "left" if city_x < mid_x else "right"
        va = "bottom" if city_y < mid_y else "top"
        horiz_offset = 1 if ha == "left" else -1
        vert_offset = 1 if va == "bottom" else -1
    
    offset_x = (xmax - xmin) * 0.01 * horiz_offset
    offset_y = (ymax - ymin) * 0.01 * vert_offset
    
    ax.text(
        city_x + offset_x, city_y + offset_y, name,
        fontsize=14, fontweight="bold", fontproperties=bradley_prop,
        color="black", va=va, ha=ha, zorder=7,
        bbox=dict(facecolor="white", alpha=0.3, edgecolor="none", pad=2)
    )

def set_exif_date_piexif(output_file, reference_img):
    try:
        dt_orig = None
        if os.path.exists(reference_img) and reference_img.lower().endswith((".jpg", ".jpeg")):
            img = Image.open(reference_img)
            exif_dict = piexif.load(img.info.get("exif", b""))
            dt_bytes = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
            if dt_bytes:
                dt_orig = datetime.datetime.strptime(dt_bytes.decode(), "%Y:%m:%d %H:%M:%S")
        if dt_orig is None:
            dt_orig = datetime.datetime.fromtimestamp(os.path.getctime(reference_img))
        dt_new = dt_orig - datetime.timedelta(seconds=10)
        exif_dict_new = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
        dt_str = dt_new.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict_new["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
        exif_dict_new["0th"][piexif.ImageIFD.DateTime] = dt_str.encode()
        exif_dict_new["0th"][piexif.ImageIFD.Rating] = 5
        exif_bytes = piexif.dump(exif_dict_new)
        img_out = Image.open(output_file)
        img_out.save(output_file, "JPEG", exif=exif_bytes)
        log("✅ Date taken appliquée avec piexif")
    except Exception as e:
        log(f"⚠ Impossible d'appliquer la date EXIF : {e}")

def get_cache_key(xmin, ymin, xmax, ymax, zoom):
    return hashlib.md5(f"{xmin:.6f}_{ymin:.6f}_{xmax:.6f}_{ymax:.6f}_z{zoom}".encode()).hexdigest()

def get_or_download_basemap(ax, xmin, ymin, xmax, ymax, zoom):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = get_cache_key(xmin, ymin, xmax, ymax, zoom)
    img_path = os.path.join(CACHE_DIR, f"{key}.png")
    bounds_path = os.path.join(CACHE_DIR, f"{key}_bounds.pkl")
    if os.path.exists(img_path) and os.path.exists(bounds_path):
        log("📂 Chargement du fond de carte depuis le cache")
        with open(bounds_path, "rb") as f:
            extent = pickle.load(f)
        img = Image.open(img_path)
        ax.imshow(img, extent=extent, interpolation="bilinear", zorder=0)
    else:
        log("🌍 Téléchargement du fond de carte")
        img, extent = ctx.bounds2img(xmin, ymin, xmax, ymax, zoom=zoom, source=ctx.providers.OpenStreetMap.France)
        ax.imshow(img, extent=extent, interpolation="bilinear", zorder=0)
        Image.fromarray(img).save(img_path, "PNG")
        with open(bounds_path, "wb") as f:
            pickle.dump(extent, f)

def geocode_city(city, xmin, ymin, xmax, ymax):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        viewbox_str = f"{xmin:.6f},{ymin:.6f},{xmax:.6f},{ymax:.6f}"
        params = {"q": city, "format": "json", "viewbox": viewbox_str, "bounded": 1}
        log(f"🔍 Géocodage '{city}' avec viewbox={viewbox_str}")
        r = requests.get(url, params=params, headers={"User-Agent": "gpx_mapper"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        log(f"   → Réponse Nominatim = {len(data) if data else 0} résultats")
        if data:
            lon, lat = float(data[0]["lon"]), float(data[0]["lat"])
            return Point(lon, lat)
        else:
            # Si aucun résultat avec bounded, essayer sans
            log(f"⚠ Aucun résultat pour '{city}' dans la viewbox, nouvelle tentative sans limites géographiques")
            params_no_bound = {"q": city, "format": "json"}
            r = requests.get(url, params=params_no_bound, headers={"User-Agent": "gpx_mapper"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data:
                lon, lat = float(data[0]["lon"]), float(data[0]["lat"])
                log(f"⚠ '{city}' trouvée en dehors de la zone (lon={lon:.4f}, lat={lat:.4f})")
                return Point(lon, lat)
    except Exception as e:
        log(f"⚠ Erreur géocodage ville '{city}' : {e}")
    return None

def draw_arrows(ax, line_proj, min_spacing=500):
    """Dessine des flèches pleines avec queue le long de la ligne (EPSG:3857)."""
    coords = np.array(line_proj.coords)
    distances = np.sqrt(np.sum(np.diff(coords, axis=0)**2, axis=1))
    cumdist = np.concatenate(([0], np.cumsum(distances)))

    indices = [0]
    last_d = 0
    for i, d in enumerate(cumdist):
        if d - last_d >= min_spacing:
            indices.append(i)
            last_d = d
    indices.append(len(coords) - 1)

    for i in range(len(indices) - 1):
        x0, y0 = coords[indices[i]]
        x1, y1 = coords[indices[i + 1]]
        arrow = FancyArrowPatch(
            (x0, y0), (x1, y1),
            arrowstyle="simple,head_length=2,head_width=4,tail_width=2",
            linewidth=0.5, edgecolor="black", facecolor="cyan", shrinkA=0, shrinkB=0, zorder=4
        )
        ax.add_patch(arrow)

def draw_flag(ax, x, y, color, extent_width):
    """Dessine un drapeau simple et clean à la position (x, y).
    color: 'green' ou 'red'
    extent_width: largeur de l'extent pour adapter la taille
    """
    # Adapter la taille du drapeau à l'extent (3% de la largeur)
    size = extent_width * 0.03
    flag_width = size * 0.5
    flag_height = size * 0.4
    
    if color == 'green':
        flag_color = '#27ae60'
        edge_color = '#1e8449'
        mat_color = '#2c3e50'
    else:  # red
        flag_color = '#c0392b'
        edge_color = '#a93226'
        mat_color = '#2c3e50'
    
    # Mât du drapeau
    ax.plot([x, x], [y, y + size], color=mat_color, linewidth=3, zorder=6, solid_capstyle='round')
    
    # Drapeau rectangulaire simple
    flag_rect = Polygon(
        [[x, y + size - flag_height], [x + flag_width, y + size - flag_height], 
         [x + flag_width, y + size], [x, y + size]],
        facecolor=flag_color,
        edgecolor=edge_color,
        linewidth=1.5,
        zorder=6
    )
    ax.add_patch(flag_rect)

def parse_date_range(args):
    """Convertit les arguments en range de datetime (timezone France), ou retourne None si aucun filtre"""
    tz_france = ZoneInfo("Europe/Paris")
    
    if args.date:
        try:
            date = datetime.datetime.strptime(args.date, "%Y-%m-%d")
            start = date.replace(hour=0, minute=0, second=0, tzinfo=tz_france)
            end = date.replace(hour=23, minute=59, second=59, tzinfo=tz_france)
            return start, end
        except ValueError as e:
            log(f"Erreur format date: {e}")
            sys.exit(1)
    
    elif args.range:
        try:
            start = datetime.datetime.strptime(args.range[0], "%Y-%m-%d %H:%M:%S")
            end = datetime.datetime.strptime(args.range[1], "%Y-%m-%d %H:%M:%S")
            
            # Ajouter la timezone France
            start = start.replace(tzinfo=tz_france)
            end = end.replace(tzinfo=tz_france)
            
            if start > end:
                log("Erreur: la date de début doit être antérieure à la date de fin")
                sys.exit(1)
            
            return start, end
        except ValueError as e:
            log(f"Erreur format datetime: {e}")
            sys.exit(1)
    
    else:
        return None

def parse_ville(ville_str):
    """Parse une ville avec nom d'affichage et position optionnels
    Format: ville ou ville:nom_affichage ou ville:nom_affichage:position
    Retourne un tuple (ville, nom_affichage, position)
    où position est None (auto) ou une chaîne comme 'N', 'SE', 'NO', etc.
    """
    parts = ville_str.split(':', 2)
    
    ville = parts[0]
    nom_affichage = parts[1] if len(parts) > 1 and parts[1] else ville
    position = parts[2] if len(parts) > 2 else None
    
    return (ville, nom_affichage, position)

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Traiter un fichier GPX avec dates et villes",
        usage="script.py fichier.gpx nom_cible [--date DATE | --range DEBUT FIN] --ville ville1[:nom1[:pos1]] [--ville ville2[:nom2[:pos2]] ...] [--image ref_image.jpg] [--marge METRES] [--titre TITRE]"
    )
    
    parser.add_argument("gpx_file", help="Fichier GPX à traiter")
    parser.add_argument("nom_cible", help="Nom du fichier cible (sans extension, .jpg sera ajouté)")
    
    date_group = parser.add_mutually_exclusive_group(required=False)
    date_group.add_argument(
        "--date", 
        type=str,
        help="Une date au format YYYY-MM-DD (range 00:00:00 à 23:59:59)"
    )
    date_group.add_argument(
        "--range",
        nargs=2,
        metavar=("DEBUT", "FIN"),
        help="Range de temps: YYYY-MM-DD HH:MM:SS YYYY-MM-DD HH:MM:SS"
    )
    
    parser.add_argument(
        "--ville",
        action="append",
        dest="villes",
        default=[],
        help="Ville à inclure, format: ville ou ville:nom_affichage ou ville:nom_affichage:position (peut être utilisé plusieurs fois). Position: N, S, E, O ou combinaisons (NE, NO, SE, SO)"
    )
    
    parser.add_argument(
        "--image",
        type=str,
        help="Image de référence (optionnel)"
    )
    
    parser.add_argument(
        "--marge",
        type=int,
        default=None,
        help="Marge autour de la trace en mètres (optionnel). Si absent, la valeur est calculée automatiquement en fonction du zoom"
    )
    
    parser.add_argument(
        "--titre",
        type=str,
        default=None,
        help="Titre à afficher en haut à gauche de la carte (optionnel)"
    )
    
    return parser.parse_args()

def generate_map(gpx_file, start_time, end_time, city_list, output_filename, ref_image=None, marge=None, titre=None):
    log("📖 Lecture du fichier GPX")
    with open(gpx_file, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    # Les paramètres start_time et end_time sont en timezone France (aware)
    # Les points GPX sont généralement en UTC (aware)
    # On rend tout naïf en heure France pour la comparaison
    tz_france = ZoneInfo("Europe/Paris")
    
    # Rendre naïf start_time et end_time (supprimer la timezone mais garder l'heure France)
    if start_time is not None and start_time.tzinfo is not None:
        start_time = start_time.replace(tzinfo=None)
    if end_time is not None and end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                if p.time:
                    # Convertir le temps du GPX en timezone France
                    p_time = p.time
                    if p_time.tzinfo is not None:
                        # Le temps est aware (ex: UTC), le convertir en France
                        p_time = p_time.astimezone(tz_france).replace(tzinfo=None)
                    # Sinon p_time est déjà naïf
                    
                    # Comparaison avec start_time et end_time (qui sont naïfs, en heure France)
                    if start_time is None or end_time is None:
                        points.append((p.longitude, p.latitude))
                    elif start_time <= p_time <= end_time:
                        points.append((p.longitude, p.latitude))

    if len(points) < 2:
        raise ValueError(f"Pas assez de points entre {start_time} et {end_time} pour générer une trace.")
    log(f"✅ {len(points)} points trouvés entre {start_time} et {end_time}")

    line = LineString(points)
    gdf_line = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")
    gdf_line_proj = gdf_line.to_crs(epsg=3857)
    xmin_deg, ymin_deg, xmax_deg, ymax_deg = gdf_line.total_bounds

    # Calcul du zoom avec une marge provisoire pour déterminer le zoom final
    width_px, height_px = 12 * 300, 9 * 300
    temp_buffered = gdf_line_proj.buffer(1000)
    xmin_temp, ymin_temp, xmax_temp, ymax_temp = temp_buffered.total_bounds
    zoom = calculate_zoom_for_extent(xmin_temp, ymin_temp, xmax_temp, ymax_temp, width_px, height_px)
    log(f"🔭 Zoom : {zoom}")
    
    # Déterminer la taille du buffer
    if marge is not None:
        buffer_size = marge
        log(f"📏 Marge : {marge}m (spécifiée)")
    else:
        # Marge proportionnelle au zoom (1000m pour zoom=12)
        buffer_size = 3000 * (2 ** (12 - zoom))
        log(f"📏 Marge calculée : {buffer_size:.0f}m")
    
    buffered = gdf_line_proj.buffer(buffer_size)
    xmin, ymin, xmax, ymax = buffered.total_bounds
    
    # Convertir les limites buffered en degrés (EPSG:4326) pour le géocodage
    # Créer un GeoDataFrame pour bien gérer la conversion de CRS
    gdf_buffered = gpd.GeoDataFrame(geometry=[buffered.union_all()], crs="EPSG:3857")
    gdf_buffered_deg = gdf_buffered.to_crs(epsg=4326)
    xmin_buff_deg, ymin_buff_deg, xmax_buff_deg, ymax_buff_deg = gdf_buffered_deg.total_bounds

    # Géocodage des villes avec vérification dans la zone buffered
    city_points = []
    for ville, nom_affichage, position in city_list:
        pt = geocode_city(ville, xmin_buff_deg, ymin_buff_deg, xmax_buff_deg, ymax_buff_deg)
        if pt:
            # Convertir le point en EPSG:3857 pour la comparaison avec buffered
            pt_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(epsg=3857)
            pt_geom = pt_proj.geometry.iloc[0]
            
            # Vérification simple par boîte englobante
            is_contained = (xmin <= pt_geom.x <= xmax) and (ymin <= pt_geom.y <= ymax)
            
            if is_contained:
                forced_pos = parse_position(position) if position else None
                city_points.append((nom_affichage, pt, forced_pos))
            else:
                log(f"⚠ Ville '{ville}' en dehors du périmètre de la piste (avec marge {buffer_size:.0f}m), ignorée")

    xmin, ymin, xmax, ymax = buffered.total_bounds

    # Ajuster les bounds pour respecter le ratio 4:3
    xmin, ymin, xmax, ymax = adjust_bounds_to_ratio(xmin, ymin, xmax, ymax, target_ratio=4/3)

    fig, ax = plt.subplots(figsize=(12, 9))

    width_px, height_px = 12 * 300, 9 * 300
    
    draw_arrows(ax, gdf_line_proj.geometry[0], 1000 / (2 ** (zoom - 12)))

    # Récupérer les points de départ et d'arrivée en projection EPSG:3857
    start_point_proj = gdf_line_proj.geometry[0].coords[0]
    end_point_proj = gdf_line_proj.geometry[0].coords[-1]
    
    # Dessiner les drapeaux avec l'extent pour adapter la taille
    extent_width = xmax - xmin
    draw_flag(ax, start_point_proj[0], start_point_proj[1], 'green', extent_width)
    draw_flag(ax, end_point_proj[0], end_point_proj[1], 'red', extent_width)

    for name, pt, forced_pos in city_points:
        city_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(epsg=3857)
        cx, cy = city_proj.geometry.x[0], city_proj.geometry.y[0]
        ax.scatter(cx, cy, s=75, c="white", edgecolor="black", zorder=5)
        ax.scatter(cx, cy, s=50, c="lightgreen", zorder=6)
        adjust_text_position(cx, cy, xmin, xmax, ymin, ymax, ax, name, forced_pos)

    get_or_download_basemap(ax, xmin, ymin, xmax, ymax, zoom)

    # Ajouter le titre en haut à gauche si fourni
    if titre:
        # Calculer les marges (2% de la largeur et hauteur)
        margin_x = (xmax - xmin) * 0.02
        margin_y = (ymax - ymin) * 0.02
        ax.text(
            xmin + margin_x, ymax - margin_y, titre,
            fontsize=18, fontweight="bold", fontproperties=bradley_prop,
            color="black", va="top", ha="left", zorder=8,
            bbox=dict(facecolor="white", alpha=0.2, edgecolor="none", pad=5)
        )

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_axis_off()

    output_file = f"{output_filename}.jpg"
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close()
    buf.seek(0)
    Image.open(buf).convert("RGB").save(output_file, "JPEG")
    log(f"✅ Fichier généré : {output_file}")

    if ref_image and os.path.exists(ref_image):
        set_exif_date_piexif(output_file, ref_image)

if __name__ == "__main__":
    args = parse_arguments()
    
    date_result = parse_date_range(args)
    if date_result:
        start_time, end_time = date_result
    else:
        start_time, end_time = None, None
    
    city_list = [parse_ville(v) for v in args.villes]
    
    log(f"Fichier GPX: {args.gpx_file}")
    log(f"Nom cible: {args.nom_cible}")
    if start_time and end_time:
        log(f"Range temporel: {start_time} -> {end_time}")
    else:
        log("Range temporel: aucun filtre (tous les points)")
    log("Villes:")
    for ville, nom_affichage, position in city_list:
        pos_str = f" (position: {position})" if position else ""
        if ville != nom_affichage:
            log(f"  {ville} (affiché comme: {nom_affichage}){pos_str}")
        else:
            log(f"  {ville}{pos_str}")
    if args.image:
        log(f"Image de référence: {args.image}")
    if args.marge:
        log(f"Marge: {args.marge}m")
    if args.titre:
        log(f"Titre: {args.titre}")
    
    generate_map(args.gpx_file, start_time, end_time, city_list, args.nom_cible, args.image, args.marge, args.titre)