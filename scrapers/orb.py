import re
import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
from config import URL_ORB_SEARCH, HEADERS
from utils import fix_image_url, cf_decode_email

# ================= REGEX & UTILIDADES =================

# Regex para frecuencia robusta
REGEX_FREQ_STRICT = re.compile(r'\b(\d{2,4}(?:\.\d{1,2})?)\s?(MHz|kHz|AM|FM)\b', re.IGNORECASE)
REGEX_FREQ_LOOSE = re.compile(r'\b(8[7-9]\.\d|9\d\.\d|10\d\.\d|5[3-9]0|[6-9]\d0|1\d{3}0|1[0-6]\d0|1700)\b')

def extract_freq_robust(text):
    """Extrae frecuencia ignorando teléfonos y años."""
    if not text: return None
    match = REGEX_FREQ_STRICT.search(text)
    if match: return f"{match.group(1)} {match.group(2).upper()}"
    
    match_loose = REGEX_FREQ_LOOSE.search(text)
    if match_loose:
        val = float(match_loose.group(1))
        if 87.5 <= val <= 108: return f"{val} FM"
        if 530 <= val <= 1700: return f"{int(val)} AM"
    return None

def extract_email_power(soup_element):
    """
    Estrategia nuclear para encontrar el email:
    1. Busca data-cfemail en el propio link.
    2. Busca data-cfemail en hijos (spans).
    3. Busca en el href si es una redirección de Cloudflare.
    4. Busca mailto simple.
    5. Busca texto plano con @.
    """
    if not soup_element: return None

    # 1. Buscar token en atributo
    cf_token = soup_element.get('data-cfemail')
    
    # 2. Buscar token en hijos (spans)
    if not cf_token:
        child_span = soup_element.find(attrs={"data-cfemail": True})
        if child_span: cf_token = child_span.get('data-cfemail')
    
    # 3. Buscar token en href (redirección)
    href = soup_element.get('href', '')
    if not cf_token and "/cdn-cgi/l/email-protection#" in href:
        cf_token = href.split('#')[-1]

    # DECODIFICAR SI HAY TOKEN
    if cf_token: 
        return cf_decode_email(cf_token)

    # 4. Mailto clásico
    if 'mailto:' in href:
        return href.replace('mailto:', '').split('?')[0].strip()

    # 5. Texto plano (último recurso)
    text = soup_element.get_text(strip=True)
    if '@' in text and '.' in text:
        return text

    return None

# ================= SCRAPER PRINCIPAL =================

def scrape_orb_v10(station_name):
    # Pausa aleatoria para evitar bloqueo
    time.sleep(random.uniform(1.0, 2.0))

    # Estructura de datos completa
    data = { 
        'logo': None, 'description': None, 'address': None, 'phone': None, 
        'email': None, 'site': None, 'whatsapp': None, 'fb': None, 
        'tw': None, 'insta': None, 'yt': None, 'tiktok': None,
        'location_parts': [], # Mantenemos esto para compatibilidad con main.py
        'country': None, 'state': None, 'city': None, # Nuevos campos separados
        'tags': None, 'orb_freq': None, 'stream_url': None,
        'orb_url': None, 'language': None # Nuevo campo idioma
    }
    
    # Inicializamos variables para evitar errores
    res = None
    full_url = None
    
    try:
        print(f"   Searching ORB for: {station_name}...")
        search_url = URL_ORB_SEARCH.format(quote_plus(station_name))
        
        # 1. Petición de Búsqueda
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        
        if r.status_code != 200:
            print(f"   [!] Error HTTP {r.status_code} en búsqueda.")
            return data

        soup = BeautifulSoup(r.text, 'html.parser')
        res = soup.select_one('ul.stations-list li a[href^="/us/"]')
        
        if not res: 
            print("   [!] No station found in list.")
            return data 
        
        # 2. Construir URL y guardarla
        full_url = urljoin("https://onlineradiobox.com", res['href'])
        data['orb_url'] = full_url
        print(f"   -> Found URL: {full_url}")

        # 3. Petición a la Página de Detalle
        r_page = requests.get(full_url, headers=HEADERS, timeout=10)
        soup_page = BeautifulSoup(r_page.text, 'html.parser')
        
        # --- EXTRACCIÓN DE DATOS ---
        
        # A. LOGO (Intento doble)
        fig = soup_page.select_one('figure.station_logo img')
        if fig: data['logo'] = fix_image_url(fig.get('src'))
        elif soup_page.find('img', attrs={'itemprop': 'image'}):
             data['logo'] = fix_image_url(soup_page.find('img', attrs={'itemprop': 'image'}).get('src'))

        # B. LOCATION (Separada y Lista)
        bc_items = soup_page.select('ul.breadcrumbs li[itemprop="itemListElement"] span[itemprop="name"]')
        locs = [x.get_text(strip=True) for x in bc_items]
        data['location_parts'] = locs # Para compatibilidad
        
        if len(locs) > 0: data['country'] = locs[0]
        if len(locs) > 1: data['state'] = locs[1]
        if len(locs) > 2: data['city'] = locs[2]

        # C. TAGS (Estrategia agresiva por URL /genre/)
        genre_links = soup_page.select('a[href*="/genre/"]')
        seen_tags = set()
        for link in genre_links:
            seen_tags.add(link.get_text(strip=True))
        
        if seen_tags:
            data['tags'] = ", ".join(list(seen_tags))
        else:
            # Fallback clásico
            tags_list = soup_page.select('ul.station_tags li a')
            if tags_list:
                data['tags'] = ", ".join([t.get_text(strip=True) for t in tags_list])

        # D. IDIOMA (Estrategia Triple)
        lang_val = None
        lang_li = soup_page.select_one('li.station_reference_lang') # 1. Clase específica
        if lang_li:
            lang_val = lang_li.get_text(strip=True)
        
        if not lang_val:
            lang_link = soup_page.select_one('a[href*="/search?l="]') # 2. Link de búsqueda de idioma
            if lang_link:
                lang_val = lang_link.get_text(strip=True)
        
        data['language'] = lang_val

        # E. STREAM Y DESCRIPCIÓN
        btn_play = soup_page.select_one('button.station_play')
        if btn_play and btn_play.get('stream'):
            data['stream_url'] = btn_play.get('stream')

        desc_div = soup_page.find('div', attrs={'itemprop': 'description'})
        if desc_div:
            data['description'] = desc_div.get_text(separator=' ', strip=True)

        # F. CONTACTOS (TABLA)
        table = soup_page.find('table', attrs={'role': 'complementary'})
        if table:
            # Dirección
            addr = table.find('span', attrs={'itemprop': 'address'})
            if addr: data['address'] = addr.get_text(separator=' ', strip=True)
            
            # Teléfono
            tel = table.find('a', attrs={'itemprop': 'telephone'})
            if tel: data['phone'] = tel.get_text().strip()
            
            # Email (USANDO ESTRATEGIA NUCLEAR)
            mail_link = table.find('a', attrs={'itemprop': 'email'})
            data['email'] = extract_email_power(mail_link)

            # Sitio Web
            site = table.find('a', attrs={'itemprop': 'url'})
            if site: data['site'] = site['href']

            # Redes Sociales
            links = table.find_all('a', href=True)
            for l in links:
                h = l['href'].lower()
                if 'wa.me' in h: data['whatsapp'] = l['href']
                elif 'facebook.com' in h: data['fb'] = l['href']
                elif 'twitter.com' in h or 'x.com' in h: data['tw'] = l['href']
                elif 'instagram.com' in h: data['insta'] = l['href']
                elif 'youtube.com' in h: data['yt'] = l['href']
                elif 'tiktok.com' in h: data['tiktok'] = l['href']

        # G. FRECUENCIA
        h1 = soup_page.find('h1', attrs={'itemprop': 'name'})
        h1_text = h1.get_text() if h1 else ""
        freq_found = extract_freq_robust(h1_text)
        
        if not freq_found and data['description']:
            freq_found = extract_freq_robust(data['description'])
            
        data['orb_freq'] = freq_found
        
        # Log Informativo
        if data['email'] or data['phone']:
            print(f"   [OK] Data: {data['email']} | {data['phone']} | Lang: {data['language']}")

    except Exception as e:
        print(f"   [ERROR] ORB Scraper failed: {e}")
        pass
        
    return data