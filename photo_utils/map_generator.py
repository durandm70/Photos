"""
Module de génération de cartes depuis fichiers GPX
Extrait et adapté depuis GenererCarte.py
"""
import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import contextily as ctx
from shapely.geometry import LineString, Point
import geopandas as gpd
from PIL import Image
from io import BytesIO
import os
import hashlib
import pickle
import matplotlib.font_manager as fm
import piexif
import requests
import numpy as np
from matplotlib.patches import FancyArrowPatch, Polygon
import gpxpy

CACHE_DIR = "__cache"


def log(msg, callback=None):
    """Affiche un message de log"""
    message = f"➡ {msg}"
    if callback:
        callback(message)
    else:
        print(message)


# Chargement de la police Bradley
try:
    bradley_path = r"C:\\Windows\\Fonts\\ARLRDBD.TTF"
    bradley_prop = fm.FontProperties(fname=bradley_path, weight="bold")
except:
    bradley_prop = None


def calculate_zoom_for_extent(xmin, ymin, xmax, ymax, width_px, height_px):
    """Calcule le niveau de zoom optimal pour l'étendue donnée"""
    lon_length = xmax - xmin
    lat_length = ymax - ymin
    zoom_lon = np.log2(156543.03 * width_px / lon_length)
    zoom_lat = np.log2(156543.03 * height_px / lat_length)
    zoom = int(min(zoom_lon, zoom_lat))
    return max(0, min(zoom, 18))


def parse_position(position_str):
    """
    Parse une chaîne de position (N, S, E, O, NE, NO, SE, SO)
    Retourne (ha, va, offset_mult)
    """
    if not position_str:
        return None

    position_str = position_str.upper()

    va = "center"
    vert_offset = 0
    if 'N' in position_str:
        va = "bottom"
        vert_offset = 1
    elif 'S' in position_str:
        va = "top"
        vert_offset = -1

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
    """Ajuste la position du texte d'une ville sur la carte"""
    if forced_position:
        ha, va, horiz_offset, vert_offset = forced_position
    else:
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


def set_exif_date_piexif(output_file, reference_img, log_callback=None, start_time=None):
    """Applique la date EXIF à partir d'une image de référence ou d'une date de départ"""
    try:
        dt_orig = None

        # Essayer d'extraire la date depuis l'image de référence
        if reference_img and os.path.exists(reference_img) and reference_img.lower().endswith((".jpg", ".jpeg")):
            img = Image.open(reference_img)
            exif_dict = piexif.load(img.info.get("exif", b""))
            dt_bytes = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
            if dt_bytes:
                dt_orig = datetime.datetime.strptime(dt_bytes.decode(), "%Y:%m:%d %H:%M:%S")
            if dt_orig is None:
                dt_orig = datetime.datetime.fromtimestamp(os.path.getctime(reference_img))
            dt_new = dt_orig - datetime.timedelta(seconds=10)
            log("✅ Date extraite de l'image de référence", log_callback)
        # Si pas d'image de référence mais start_time fourni, utiliser start_time
        elif start_time is not None:
            dt_new = start_time
            log("✅ Utilisation de la date de départ du tracé", log_callback)
        else:
            log("⚠ Aucune source de date disponible", log_callback)
            return

        # Appliquer les métadonnées EXIF
        exif_dict_new = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
        dt_str = dt_new.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict_new["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode()
        exif_dict_new["0th"][piexif.ImageIFD.DateTime] = dt_str.encode()
        exif_dict_new["0th"][piexif.ImageIFD.Rating] = 5
        exif_bytes = piexif.dump(exif_dict_new)
        img_out = Image.open(output_file)
        img_out.save(output_file, "JPEG", exif=exif_bytes)
        log("✅ Date taken et rating (5★) appliqués avec piexif", log_callback)
    except Exception as e:
        log(f"⚠ Impossible d'appliquer la date EXIF : {e}", log_callback)


def get_cache_key(xmin, ymin, xmax, ymax, zoom):
    """Génère une clé de cache pour une étendue et un zoom donnés"""
    return hashlib.md5(f"{xmin:.6f}_{ymin:.6f}_{xmax:.6f}_{ymax:.6f}_z{zoom}".encode()).hexdigest()


def get_or_download_basemap(ax, xmin, ymin, xmax, ymax, zoom, log_callback=None):
    """Récupère ou télécharge le fond de carte"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = get_cache_key(xmin, ymin, xmax, ymax, zoom)
    img_path = os.path.join(CACHE_DIR, f"{key}.png")
    bounds_path = os.path.join(CACHE_DIR, f"{key}_bounds.pkl")
    if os.path.exists(img_path) and os.path.exists(bounds_path):
        log("📂 Chargement du fond de carte depuis le cache", log_callback)
        with open(bounds_path, "rb") as f:
            extent = pickle.load(f)
        img = Image.open(img_path)
        ax.imshow(img, extent=extent, interpolation="bilinear", zorder=0)
    else:
        log("🌍 Téléchargement du fond de carte", log_callback)
        img, extent = ctx.bounds2img(xmin, ymin, xmax, ymax, zoom=zoom, source=ctx.providers.OpenStreetMap.France)
        ax.imshow(img, extent=extent, interpolation="bilinear", zorder=0)
        Image.fromarray(img).save(img_path, "PNG")
        with open(bounds_path, "wb") as f:
            pickle.dump(extent, f)


def geocode_city(city, xmin, ymin, xmax, ymax, log_callback=None):
    """Géocode une ville dans l'étendue donnée"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        viewbox_str = f"{xmin:.6f},{ymin:.6f},{xmax:.6f},{ymax:.6f}"
        params = {"q": city, "format": "json", "viewbox": viewbox_str, "bounded": 1}
        log(f"🔍 Géocodage '{city}' avec viewbox={viewbox_str}", log_callback)
        r = requests.get(url, params=params, headers={"User-Agent": "gpx_mapper"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        log(f"   → Réponse Nominatim = {len(data) if data else 0} résultats", log_callback)
        if data:
            lon, lat = float(data[0]["lon"]), float(data[0]["lat"])
            return Point(lon, lat)
        else:
            log(f"⚠ Aucun résultat pour '{city}' dans la viewbox, nouvelle tentative sans limites", log_callback)
            params_no_bound = {"q": city, "format": "json"}
            r = requests.get(url, params=params_no_bound, headers={"User-Agent": "gpx_mapper"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data:
                lon, lat = float(data[0]["lon"]), float(data[0]["lat"])
                log(f"⚠ '{city}' trouvée en dehors de la zone (lon={lon:.4f}, lat={lat:.4f})", log_callback)
                return Point(lon, lat)
    except Exception as e:
        log(f"⚠ Erreur géocodage ville '{city}' : {e}", log_callback)
    return None


def draw_arrows(ax, line_proj, min_spacing=500):
    """Dessine des flèches pleines avec queue le long de la ligne"""
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
    """Dessine un drapeau à la position (x, y)"""
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

    ax.plot([x, x], [y, y + size], color=mat_color, linewidth=3, zorder=6, solid_capstyle='round')

    flag_rect = Polygon(
        [[x, y + size - flag_height], [x + flag_width, y + size - flag_height],
         [x + flag_width, y + size], [x, y + size]],
        facecolor=flag_color,
        edgecolor=edge_color,
        linewidth=1.5,
        zorder=6
    )
    ax.add_patch(flag_rect)


def parse_ville(ville_str):
    """
    Parse une ville avec nom d'affichage et position optionnels
    Format: ville ou ville:nom_affichage ou ville:nom_affichage:position
    """
    parts = ville_str.split(':', 2)

    ville = parts[0]
    nom_affichage = parts[1] if len(parts) > 1 and parts[1] else ville
    position = parts[2] if len(parts) > 2 else None

    return (ville, nom_affichage, position)


def generate_map(gpx_file, start_time, end_time, city_list, output_filename,
                 ref_image=None, marge=None, titre=None, log_callback=None):
    """
    Génère une carte depuis un fichier GPX

    Args:
        gpx_file: Chemin du fichier GPX
        start_time: Date/heure de début (datetime aware ou None pour tous les points)
        end_time: Date/heure de fin (datetime aware ou None pour tous les points)
        city_list: Liste de tuples (ville, nom_affichage, position)
        output_filename: Nom du fichier de sortie (sans extension)
        ref_image: Image de référence pour la date EXIF (optionnel)
        marge: Marge autour de la trace en mètres (optionnel)
        titre: Titre à afficher sur la carte (optionnel)
        log_callback: Fonction de callback pour les logs (optionnel)
    """
    log("📖 Lecture du fichier GPX", log_callback)
    with open(gpx_file, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    tz_france = ZoneInfo("Europe/Paris")

    # Rendre naïf start_time et end_time
    if start_time is not None and start_time.tzinfo is not None:
        start_time = start_time.replace(tzinfo=None)
    if end_time is not None and end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                if p.time:
                    p_time = p.time
                    if p_time.tzinfo is not None:
                        p_time = p_time.astimezone(tz_france).replace(tzinfo=None)

                    if start_time is None or end_time is None:
                        points.append((p.longitude, p.latitude))
                    elif start_time <= p_time <= end_time:
                        points.append((p.longitude, p.latitude))

    if len(points) < 2:
        raise ValueError(f"Pas assez de points entre {start_time} et {end_time} pour générer une trace.")
    log(f"✅ {len(points)} points trouvés", log_callback)

    line = LineString(points)
    gdf_line = gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326")
    gdf_line_proj = gdf_line.to_crs(epsg=3857)

    width_px, height_px = 12 * 300, 9 * 300
    temp_buffered = gdf_line_proj.buffer(1000)
    xmin_temp, ymin_temp, xmax_temp, ymax_temp = temp_buffered.total_bounds
    zoom = calculate_zoom_for_extent(xmin_temp, ymin_temp, xmax_temp, ymax_temp, width_px, height_px)
    log(f"🔭 Zoom : {zoom}", log_callback)

    if marge is not None:
        buffer_size = marge
        log(f"📏 Marge : {marge}m (spécifiée)", log_callback)
    else:
        buffer_size = 3000 * (2 ** (12 - zoom))
        log(f"📏 Marge calculée : {buffer_size:.0f}m", log_callback)

    buffered = gdf_line_proj.buffer(buffer_size)
    xmin, ymin, xmax, ymax = buffered.total_bounds

    gdf_buffered = gpd.GeoDataFrame(geometry=[buffered.union_all()], crs="EPSG:3857")
    gdf_buffered_deg = gdf_buffered.to_crs(epsg=4326)
    xmin_buff_deg, ymin_buff_deg, xmax_buff_deg, ymax_buff_deg = gdf_buffered_deg.total_bounds

    # Géocodage des villes
    city_points = []
    for ville, nom_affichage, position in city_list:
        pt = geocode_city(ville, xmin_buff_deg, ymin_buff_deg, xmax_buff_deg, ymax_buff_deg, log_callback)
        if pt:
            pt_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(epsg=3857)
            pt_geom = pt_proj.geometry.iloc[0]

            is_contained = (xmin <= pt_geom.x <= xmax) and (ymin <= pt_geom.y <= ymax)

            if is_contained:
                forced_pos = parse_position(position) if position else None
                city_points.append((nom_affichage, pt, forced_pos))
            else:
                log(f"⚠ Ville '{ville}' en dehors du périmètre, ignorée", log_callback)

    xmin, ymin, xmax, ymax = buffered.total_bounds
    fig, ax = plt.subplots(figsize=(12, 9))

    draw_arrows(ax, gdf_line_proj.geometry[0], 1000 / (2 ** (zoom - 12)))

    start_point_proj = gdf_line_proj.geometry[0].coords[0]
    end_point_proj = gdf_line_proj.geometry[0].coords[-1]

    extent_width = xmax - xmin
    draw_flag(ax, start_point_proj[0], start_point_proj[1], 'green', extent_width)
    draw_flag(ax, end_point_proj[0], end_point_proj[1], 'red', extent_width)

    for name, pt, forced_pos in city_points:
        city_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(epsg=3857)
        cx, cy = city_proj.geometry.x[0], city_proj.geometry.y[0]
        ax.scatter(cx, cy, s=75, c="white", edgecolor="black", zorder=5)
        ax.scatter(cx, cy, s=50, c="lightgreen", zorder=6)
        adjust_text_position(cx, cy, xmin, xmax, ymin, ymax, ax, name, forced_pos)

    get_or_download_basemap(ax, xmin, ymin, xmax, ymax, zoom, log_callback)

    if titre:
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
    log(f"✅ Fichier généré : {output_file}", log_callback)

    # Appliquer les métadonnées EXIF (date taken et rating 5★)
    set_exif_date_piexif(output_file, ref_image, log_callback, start_time)
