import os
import requests
import math
from urllib.parse import urlparse
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageStat, ImageDraw

# ================= CONFIGURACIÓN DE ESTILO =================
TARGET_SIZE = (500, 500)
SCALE_UP_LIMIT = 1.5
SUPERSAMPLE_FACTOR = 2
SHARPEN_PARAMS = {'radius': 1, 'percent': 150, 'threshold': 3}
SHADOW = {'offset': (10, 10), 'blur': 18, 'opacity': 120}
PAD_EXTRA = 0.06   # % extra de pad para evitar cortar (ej: por sombras o radio)
AA_BLUR_ALPHA = 1.2  # blur en alpha para anti-alias
BG_DETECTION_TOLERANCE = 18  # tolerancia para detectar fondo parecido
BG_REQUIRED_RATIO = 0.86

# ================= HERRAMIENTAS DE PROCESAMIENTO =================

def is_solid_background(img, sample_pixels=200, tolerance=BG_DETECTION_TOLERANCE, required_ratio=BG_REQUIRED_RATIO):
    """Detecta si el fondo es sólido analizando los bordes.
    Retorna (bool, (r,g,b)) — si se detecta fondo sólido y color representativo.
    Mantiene misma firma que tu versión original."""
    img_conv = img.convert("RGBA")
    w, h = img_conv.size
    pixels = img_conv.load()
    samples = []

    # Muestrear bordes
    step_x = max(1, w // 20)
    step_y = max(1, h // 20)
    for x in range(0, w, step_x):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, h - 1])
    for y in range(0, h, step_y):
        samples.append(pixels[0, y])
        samples.append(pixels[w - 1, y])

    if len(samples) > sample_pixels:
        samples = samples[:sample_pixels]

    opaque_samples = [s for s in samples if s[3] > 10]
    if not opaque_samples:
        return False, None  # todo transparente o sin información de borde

    def rgb_no_alpha(c):
        return (c[0], c[1], c[2])

    # Encuentra color más común
    try:
        rep = max(set([rgb_no_alpha(s) for s in opaque_samples]),
                  key=lambda x: sum(1 for s in opaque_samples if rgb_no_alpha(s) == x))
    except ValueError:
        return False, None

    def color_dist(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    within = sum(1 for s in opaque_samples if color_dist(rgb_no_alpha(s), rep) <= tolerance)
    ratio = within / max(1, len(opaque_samples))

    return (ratio >= required_ratio), rep if (ratio >= required_ratio) else None


def _replace_solid_bg_with_white(img, bg_color, tolerance=BG_DETECTION_TOLERANCE, aa_blur=AA_BLUR_ALPHA):
    """Si detectamos fondo sólido, reemplaza el fondo por blanco
    preservando el antialias en los bordes (devuelve RGBA con fondo blanco)."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    # Construimos máscara basada en distancia de color al bg_color
    mask = Image.new("L", (w, h), 255)
    mask_px = mask.load()

    def color_dist(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 12:
                # transparente -> no es fondo sólido visible, mantener como 'no-fondo'
                mask_px[x, y] = 0
            else:
                d = color_dist((r, g, b), bg_color)
                if d <= tolerance:
                    # cercano al color del fondo -> marcar como fondo (255)
                    mask_px[x, y] = 255
                else:
                    mask_px[x, y] = 0

    # Suavizar la máscara para preservar antialias
    mask = mask.filter(ImageFilter.GaussianBlur(radius=aa_blur))
    # Convertir máscara a alpha invertida (0->logo, 255->fondo)
    inv_mask = ImageOps.invert(mask)

    # Crear imagen fondo blanco
    white_bg = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    # Pegar logo sobre fondo blanco usando inv_mask como alpha
    composed = Image.composite(img, white_bg, inv_mask)
    return composed


def _estimate_edge_strength(img):
    """Retorna una medida (0..255) del detalle/edges en la imagen:
    más baja -> más borrosa -> aplicar más sharpen."""
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edges)
    mean = stat.mean[0] if stat.mean else 0
    return mean


def intelligent_sharpen(pil_img, base_params=SHARPEN_PARAMS):
    """Sharpen que ajusta intensidad según cuán borrosa esté la imagen."""
    img = pil_img.convert("RGB")
    score = _estimate_edge_strength(img)
    # mapa simple: si score < 20 -> subir percent, si >60 -> bajar
    if score < 15:
        percent = min(400, base_params['percent'] + 160)
        radius = min(2.5, base_params['radius'] + 1.2)
        threshold = max(1, int(base_params['threshold'] / 2))
    elif score < 30:
        percent = min(320, base_params['percent'] + 80)
        radius = min(2.0, base_params['radius'] + 0.8)
        threshold = max(2, int(base_params['threshold'] * 0.8))
    elif score < 60:
        percent = base_params['percent']
        radius = base_params['radius']
        threshold = base_params['threshold']
    else:
        percent = max(120, int(base_params['percent'] * 0.85))
        radius = max(0.7, base_params['radius'] * 0.9)
        threshold = base_params['threshold'] + 1

    sharpened = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))
    return sharpened


def smart_resize_and_pad(img, target_size=TARGET_SIZE):
    """Redimensiona con supersample, aplica auto-pad, y devuelve RGBA centrado en canvas blanco.
    Mantiene la firma original (img -> Image)."""
    img = img.convert("RGBA")
    tw, th = target_size
    w, h = img.size

    # Considerar padding extra (por sombras/radio)
    pad_x = int(tw * PAD_EXTRA)
    pad_y = int(th * PAD_EXTRA)
    effective_tw = tw - 2 * pad_x
    effective_th = th - 2 * pad_y

    scale = min(effective_tw / w, effective_th / h)
    if scale > 1.0 and scale > SCALE_UP_LIMIT:
        scale = SCALE_UP_LIMIT

    # Supersampling upscale
    new_w = max(1, int(w * scale * SUPERSAMPLE_FACTOR))
    new_h = max(1, int(h * scale * SUPERSAMPLE_FACTOR))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if SUPERSAMPLE_FACTOR > 1:
        resized = resized.resize((int(new_w / SUPERSAMPLE_FACTOR), int(new_h / SUPERSAMPLE_FACTOR)),
                                 Image.Resampling.LANCZOS)

    # Anti-alias adicional: suavizar canal alfa
    r, g, b, a = resized.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=0.8))
    resized = Image.merge("RGBA", (r, g, b, a))

    canvas = Image.new("RGBA", (tw, th), (255, 255, 255, 255))
    left = (tw - resized.width) // 2
    top = (th - resized.height) // 2
    canvas.paste(resized, (left, top), resized)
    return canvas


def add_rounded_corners_and_shadow(img):
    """Aplica bordes redondeados suavizados y una sombra profesional.
    Recibe RGBA y devuelve RGBA de tamaño TARGET_SIZE (misma firma que antes)."""
    img = img.convert("RGBA")
    w, h = img.size

    # Radius basado en tamaño
    radius = int(min(w, h) * 0.08)

    # Crear máscara redondeada con suavizado (antialias)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
    # Suavizar la máscara para bordes más agradables
    mask = mask.filter(ImageFilter.GaussianBlur(radius=AA_BLUR_ALPHA))

    # Aplicar máscara a alpha del logo (componer)
    r, g, b, a = img.split()
    # combinar alpha existente con la máscara para mantener semitransparencias internas
    new_alpha = ImageChops.multiply(a, mask) if 'ImageChops' in globals() else Image.eval(a, lambda px: px)
    # Si ImageChops no fue importado, fallback: reemplazamos por mask para garantizar borde redondeado
    try:
        from PIL import ImageChops
        new_alpha = ImageChops.multiply(a, mask)
    except Exception:
        new_alpha = mask

    img.putalpha(new_alpha)

    # ======== Crear sombra profesional ========
    offset = SHADOW['offset']
    blur = SHADOW['blur']
    opacity = SHADOW['opacity']

    # Tamaño base para la sombra (incluimos blur y offset)
    total_w = w + abs(offset[0]) + blur * 2
    total_h = h + abs(offset[1]) + blur * 2
    base = Image.new('RGBA', (total_w, total_h), (255, 255, 255, 0))

    # Sombra: usar la alpha del logo
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    shadow.putalpha(new_alpha)

    # Pegar shadow en posición con margen de blur
    shadow_pos = (blur + max(offset[0], 0), blur + max(offset[1], 0))
    base.paste(shadow, shadow_pos, shadow)

    # Blur para suavizar
    base = base.filter(ImageFilter.GaussianBlur(radius=blur))

    # Ajustar opacidad sombra
    if opacity < 255:
        alpha = base.split()[-1].point(lambda p: p * (opacity / 255.0))
        base.putalpha(alpha)

    # Pegar el logo en el lugar correcto del base
    logo_pos = (blur + max(-offset[0], 0), blur + max(-offset[1], 0))
    base.paste(img, logo_pos, img)

    # Finalmente, centrar en canvas TARGET_SIZE y devolver
    final_canvas = Image.new("RGBA", TARGET_SIZE, (255, 255, 255, 255))
    left = (TARGET_SIZE[0] - base.width) // 2
    top = (TARGET_SIZE[1] - base.height) // 2
    final_canvas.paste(base, (left, top), base)

    # Un poco de suavizado final para logos vectorizados/PNG
    final_canvas = final_canvas.filter(ImageFilter.SMOOTH_MORE)
    return final_canvas


def process_pipeline(img_path_in, img_path_out):
    """Ejecuta toda la lógica visual. Mantiene la misma firma."""
    try:
        img = Image.open(img_path_in).convert("RGBA")

        # 1) Detectar fondo sólido
        solid, bg_color = is_solid_background(img)

        # 2) Si es sólido → convertimos el fondo a blanco preservando antialias
        if solid and bg_color:
            img = _replace_solid_bg_with_white(img, bg_color, tolerance=BG_DETECTION_TOLERANCE, aa_blur=AA_BLUR_ALPHA)
        else:
            # si no es sólido, lo dejamos tal cual (preservando transparencias)
            img = img.convert("RGBA")

        # 3) Resize + auto-pad (centrado)
        canvas = smart_resize_and_pad(img)

        # 4) Bordes redondeados + sombra
        final = add_rounded_corners_and_shadow(canvas)

        # 5) Sharpen inteligente según detalle
        final_rgb = intelligent_sharpen(final, SHARPEN_PARAMS)

        # 6) Pequeño ajuste de contraste para mejor presentación
        enhancer = ImageEnhance.Contrast(final_rgb)
        final_rgb = enhancer.enhance(1.05)

        # Guardar. Si se guarda JPEG, cuidamos la conversión (blanco de fondo ya aplicado).
        final_rgb.save(img_path_out, quality=95, optimize=True)
        return True
    except Exception as e:
        print(f"Error procesando imagen: {e}")
        return False


# ================= FUNCIÓN MAESTRA PARA EL MAIN (misma firma) =================

def download_and_process(url, slug, output_folder):
    """
    Función ÚNICA que el Main necesita llamar.
    1. Descarga a temporal.
    2. Procesa y guarda final.
    3. Limpia temporal.
    Mantiene firma y comportamiento general anterior.
    """
    if not url:
        return None

    # 1. Definir rutas
    filename_final = f"{slug}.jpg"
    path_final = os.path.join(output_folder, filename_final)

    # Si ya existe la final procesada, saltar (caché)
    if os.path.exists(path_final):
        return path_final

    # 2. Descargar archivo "crudo" (temporal)
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1] or ".jpg"
    path_temp = os.path.join(output_folder, f"temp_{slug}{ext}")

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            with open(path_temp, 'wb') as f:
                f.write(r.content)

            # 3. Procesar (La magia)
            success = process_pipeline(path_temp, path_final)

            # 4. Limpieza
            if os.path.exists(path_temp):
                try:
                    os.remove(path_temp)
                except Exception:
                    pass

            return path_final if success else None

    except Exception as e:
        print(f"Error descarga/proceso {slug}: {e}")
        if os.path.exists(path_temp):
            try:
                os.remove(path_temp)
            except Exception:
                pass
        return None
