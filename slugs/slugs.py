import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
import time
import unicodedata
from urllib.parse import quote_plus, urljoin, urlparse
from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageEnhance
import os, math
# ================= UTILIDADES DE TRANSFORMACIÓN =================
# Regex
REGEX_CALLSIGN = re.compile(r'\b([KW][A-Z0-9-]{2,4})\b', re.IGNORECASE)
REGEX_FREQ_TITLE = re.compile(r'\b(\d{2,4}(\.\d)?)\b') # Busca números flotantes
REGEX_ZIPCODE = re.compile(r'\b\d{5}(?:-\d{4})?\b') # Busca Codigo Postal USA

# Cache para slugs únicos
USED_SLUGS = []
def to_slug(text):
    """
    Port exacto de tu función JS utils/slugify.js a Python
    """
    if not text: return ""
    # 1. Eliminar diacríticos (tildes, ñ)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = text.strip()
    
    # 2. Caracteres a eliminar (Regex de tu JS)
    chars_to_remove = r'[\$\€\%\!\`\´\[\];:<>{}\(\)\+\¿\?\¡º#=,\/|@*&\\!~_"\']'
    text = re.sub(chars_to_remove, "", text)
    
    # 3. Reemplazar espacios y puntos por guiones
    text = re.sub(r'[.,\s]+', "-", text)
    
    # 4. Lowercase
    text = text.lower()
    
    # 5. Limpiar guiones repetidos
    text = re.sub(r'-+', "-", text)
    text = re.sub(r'^-+|-+$', "", text)
    
    return text

def generate_unique_slug(title, location_part=""):
    """Genera slug único, agregando contador si ya existe."""
    base = title
    if location_part: base = f"{title}-{location_part}"
    
    slug = to_slug(base)
    if not slug: slug = "radio-station" # Fallback
    
    original_slug = slug
    count = 1
    
    while slug in USED_SLUGS:
        slug = f"{original_slug}-{count}"
        count += 1
    
    USED_SLUGS.append(slug)
    return slug
