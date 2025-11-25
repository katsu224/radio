import os
import requests
import pandas as pd
import re
import time
   
# Importar Configuración
from config import (
    LIMITE_PRUEBA, CARPETA_LOGOS, URL_FCC_FM, URL_FCC_AM,
    URL_RADIO_BROWSER, HEADERS, REGEX_CALLSIGN, REGEX_ZIPCODE
)
   
# Scrapers
from scrapers.fcc import parse_fcc_visual
from scrapers.orb import scrape_orb_v10

# Módulos personalizados
from clasificadorTipo.clasificadorTipo import classify_about_type
from limpiezaTitulo.limpiezaTitulo import clean_title_extract_freq
from slugs.slugs import generate_unique_slug
from gestionDeImagenes.gestionImagen import download_and_process


def crear_carpeta():
    if not os.path.exists(CARPETA_LOGOS):
        os.makedirs(CARPETA_LOGOS)


# -------------------------------
# AUX: Normalizar frecuencia
# -------------------------------
def _normalize_freq_str(freq_raw):
    if not freq_raw:
        return None, None
    s = str(freq_raw).strip().replace(',', '.')
    m = re.search(r'([0-9]{2,4}(?:\.[0-9]+)?)', s)
    if not m:
        return None, None
    try:
        val = float(m.group(1))
        return val, ('kHz' if val > 108 else 'MHz')
    except:
        return None, None


# -------------------------------
# RESOLVER FRECUENCIA Y MODULACIÓN
# -------------------------------
def resolve_frequency_and_modulation_prefer_orb(fcc_entry, orb_entry, raw_title, rb_entry):
    """
    Prioridad: ORB (si tiene freq) -> FCC -> título -> STREAM.
    """
    # 1) ORB preferido
    if orb_entry:
        orb_freq = orb_entry.get('orb_freq')
        if orb_freq:
            val, _ = _normalize_freq_str(orb_freq)
            if val:
                if 87.5 <= val <= 108: return orb_freq, 'FM'
                if 530 <= val <= 1700: return orb_freq, 'AM'
                return orb_freq, 'FM'

    # 2) FCC
    if fcc_entry and fcc_entry.get('freq'):
        f = str(fcc_entry['freq']).strip()
        val, _ = _normalize_freq_str(f)
        if val:
            mod = fcc_entry.get('service') or ('FM' if 87.5 <= val <= 108 else 'AM')
            return f, mod

    # 3) Título
    m = re.search(r'([0-9]{2,4}(?:\.[0-9]+)?)', raw_title)
    if m:
        try:
            val = float(m.group(1))
            if 87.5 <= val <= 108: return m.group(1), 'FM'
            if 530 <= val <= 1700: return m.group(1), 'AM'
        except: pass

    # 4) Fallback
    return None, 'STREAM'


# -------------------------------
# ETL PRINCIPAL (MAIN)
# -------------------------------
def main():
    print("=== ETL RADIO V10 (DATA COMPLETA & UBICACIÓN SEPARADA) ===")
    crear_carpeta()

    print("1. Cargando FCC (FM/AM)...")
    fcc_db = {}
    fcc_db.update(parse_fcc_visual(URL_FCC_FM, "FM"))
    fcc_db.update(parse_fcc_visual(URL_FCC_AM, "AM"))

    print("2. Descargando Radio-Browser...")
    try:
        stations = requests.get(URL_RADIO_BROWSER, headers=HEADERS, timeout=15).json()
    except Exception as e:
        print(f"[ERROR] No pude descargar Radio-Browser: {e}")
        return

    batch = stations[:LIMITE_PRUEBA] if LIMITE_PRUEBA else stations
    final_data = []

    print(f"3. Procesando {len(batch)} registros...")

    for i, st in enumerate(batch):
        raw_title = st.get('name', '').strip()

        # 1. LIMPIAR TÍTULO PRIMERO (Mejor búsqueda)
        clean_title, extracted_freq = clean_title_extract_freq(raw_title, None)

        # CALLSIGN
        call_match = REGEX_CALLSIGN.search(raw_title)
        callsign = call_match.group(1).upper() if call_match else None
        fcc = fcc_db.get(callsign)
        
        # 2. SCRAPING ORB (Usando título limpio)
        orb = scrape_orb_v10(clean_title) 
        
        # Fallback con callsign
        if not orb.get('orb_url') and callsign:
             print(f"   -> Reintentando con Callsign: {callsign}")
             orb = scrape_orb_v10(callsign)

        # Debug
        if orb.get('email'):
             print(f"   [INFO] Contacto encontrado: {orb.get('email')}")

        # Resolver frecuencia
        final_freq, mod = resolve_frequency_and_modulation_prefer_orb(fcc, orb, raw_title, st)

        if mod == "STREAM" or not final_freq:
            broadcast_freq = "Stream"
            broadcast_freq_value = "Stream"
            mod = "STREAM"
        else:
            broadcast_freq = f"{final_freq} {mod}" if not str(final_freq).lower().endswith(mod.lower()) else str(final_freq)
            broadcast_freq_value = final_freq

        # --- AQUI ESTÁ EL CAMBIO DE UBICACIÓN ---
        # Priorizamos los campos separados que ahora devuelve tu nuevo orb.py
        
        country = orb.get('country')
        state = orb.get('state')
        city = orb.get('city')

        # Fallback a Radio-Browser si ORB no trajo nada
        if not country: country = st.get('country', '')
        if not state: state = st.get('state', '')
        # Si la ciudad viene vacía de ORB, a veces RB la tiene
        if not city: city = st.get('state', '') # RB a veces pone ciudad en state, cuidado aqui.

        # Postal Code
        postal = None
        if orb and orb.get('address'):
            mzip = REGEX_ZIPCODE.search(orb['address'])
            if mzip: postal = mzip.group(0)

        # Slug & Imagen
        slug_base = city if city else (state if state else "station")
        slug = generate_unique_slug(clean_title, slug_base)

        local_img = None
        if orb and orb.get('logo'):
            try:
                local_img = download_and_process(orb['logo'], slug, CARPETA_LOGOS)
            except Exception as e:
                local_img = None

        # Tags & Tipo
        tags_final = orb.get('tags') if orb and orb.get('tags') else st.get('tags', '')
        about_type = classify_about_type(tags_final)

        # Geo
        geo_lat = fcc.get('lat') if (fcc and fcc.get('lat')) else st.get('geo_lat')
        geo_long = fcc.get('lon') if (fcc and fcc.get('lon')) else st.get('geo_long')

        # --- MAPEO DEFINITIVO ---
        item = {
            "orb_url": orb.get('orb_url'),
            "title": clean_title,
            "slug": slug,
            "broadcastFrequency": broadcast_freq,
            "broadcastFrequencyValue": broadcast_freq_value,
            "broadcastSignalModulation": mod,
            "slogan": None,
            "imagen": local_img,
            "imagenurl": orb.get('logo'),
            "tags": tags_final,
            "web": orb.get('web') if orb.get('web') else st.get('homepage'), # Ojo: orb devuelve 'web' en contacts
            "address": orb.get('address'),
            "country": country,  # NUEVA COLUMNA
            "state": state,      # SEPARADO
            "city": city,        # SEPARADO
            "postalcode": postal,
            "geo_lat": geo_lat,
            "geo_long": geo_long,
            "geo_distance": None,
            "telephone": orb.get('phone'),
            "email": orb.get('email'),
            "facebook": orb.get('fb'),
            "instagram": orb.get('insta'),
            "red_x": orb.get('tw'),
            "tiktok": orb.get('tiktok'),
            "playstore": None,
              "language": orb.get('language') if orb.get('language') else st.get('language', ''),
            # --- DATOS EXTRA ---
            "content": orb.get('description'),
            "about_type": about_type,
            # --- CONTACTOS Extra---
            "whatsapp": orb.get('whatsapp'),
            "youtube": orb.get('yt')
            
        }

        final_data.append(item)

        if (i + 1) % 5 == 0:
            print(f"[{i+1}] Procesado: {slug}")

    print("4. Guardando DATA_FINAL_RADIOS_USA.xlsx ...")
    df = pd.DataFrame(final_data)

    # COLUMNAS ACTUALIZADAS (Agregado 'country' y reordenado location)
    cols = [
       "orb_url",
        "title", 
        "slug", 
        "broadcastFrequency", 
        "broadcastFrequencyValue", 
        "broadcastSignalModulation",
        "slogan", 
        "imagen", 
        "imagenurl", 
        "tags",  
        "web",
        "address",
        "country",
        "state",
        "city", 
        "postalcode",
        "geo_lat", 
        "geo_long", 
        "geo_distance", 
        "telephone",
        "email", 
        "facebook",
        "instagram", 
        "red_x", 
        "tiktok",
        "youtube", 
        "playstore", 
        "language",
        "content", 
        "about_type", 
    ]

    # Rellenar columnas faltantes
    for c in cols:
        if c not in df.columns:
            df[c] = None
            
    # Reordenar y exportar
    df = df[cols]
    df.to_excel("DATA_FINAL_RADIOS_USA.xlsx", index=False)
    print("¡MISIÓN CUMPLIDA! Datos exportados con columnas de ubicación separadas.")


if __name__ == "__main__":
    main()