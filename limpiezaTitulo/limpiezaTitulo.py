import requests
import pandas as pd
import re
from bs4 import BeautifulSoup
import time
import unicodedata
from urllib.parse import quote_plus, urljoin, urlparse
from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageEnhance
import os, math

# ================= Limpieza DE Titulo =================

REGEX_FREQ_TITLE = re.compile(
    r'\b((?:\d{2,3}\.\d{1})|\d{3,4})(?=\s?(?:fm|am|mhz|khz|$))',
    re.IGNORECASE
)

def clean_title_extract_freq(title, current_freq):
    """
    Limpia títulos de radios y extrae frecuencias AM/FM reales.
    Compatible con miles de estaciones sin LLM.
    """
    if not title:
        return "", current_freq

    original_title = title
    title = title.strip()
    new_freq = current_freq

    # SI NO TENEMOS FRECUENCIA — EXTRAER DESDE EL TÍTULO
    if not new_freq or str(new_freq) == "0":
        m = REGEX_FREQ_TITLE.search(title)
        if m:
            freq_str = m.group(1)

            # Convertir y clasificar
            try:
                val = float(freq_str)

                if 87.5 <= val <= 108.0:          # FM real
                    new_freq = f"{val}"
                    title = REGEX_FREQ_TITLE.sub("", title)
                    title = re.sub(r'\bFM\b', '', title, flags=re.I)

                elif 530 <= val <= 1710:         # AM real
                    new_freq = f"{int(val)}"
                    title = REGEX_FREQ_TITLE.sub("", title)
                    title = re.sub(r'\bAM\b', '', title, flags=re.I)

            except:
                pass

    # LIMPIEZA PROFESIONAL DEL TÍTULO
    title = re.sub(r'\b(FM|AM|MHz|kHz)\b', '', title, flags=re.I)
    title = re.sub(r'\s{2,}', ' ', title)               # espacios dobles
    title = re.sub(r'[^\w\s\-:]+$', '', title)          # símbolos al final
    title = title.strip(" -_:/\\")                      # limpiar bordes

    # Si quedó vacío, restauramos
    if not title:
        title = original_title

    return title.strip(), new_freq
