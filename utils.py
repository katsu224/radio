# utils.py

def fix_image_url(url):
    """Retorna Url de la imagen fija con https"""
    if not url: return None
    url = url.strip()
    if url.startswith('//'): return 'https:' + url
    return url

def dms_to_decimal(direction, deg, mint, sec):
    """Convierte coordenadas DMS a Decimal"""
    try:
        dd = float(deg) + float(mint)/60 + float(sec)/3600
        if direction.upper() in ['S', 'W']: dd = -dd
        return round(dd, 6)
    except: return None

def cf_decode_email(encodedString):
    """Decodifica emails protegidos por Cloudflare"""
    try:
        r = int(encodedString[:2], 16)
        email = ''.join([chr(int(encodedString[i:i+2], 16) ^ r) for i in range(2, len(encodedString), 2)])
        return email
    except: return None