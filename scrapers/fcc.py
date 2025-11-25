import requests
import re
from bs4 import BeautifulSoup
from config import HEADERS, REGEX_CALLSIGN
from utils import dms_to_decimal

def parse_fcc_visual(url, type_label):
    print(f"   -> Cargando FCC {type_label}...")
    stations = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        soup = BeautifulSoup(r.text, 'html.parser')
        lines = soup.get_text(separator=' ').splitlines()
        for line in lines:
            line = line.strip()
            if "LIC" not in line: continue
            call_match = REGEX_CALLSIGN.search(line)
            if not call_match: continue
            callsign = call_match.group(1).upper()
            
            # Frecuencia visual
            match_freq = re.search(r'(\d{2,4}\.?\d*)', line)
            freq_val = match_freq.group(1) if match_freq else ""
            
            lat_dec, lon_dec = None, None
            c_match = re.search(r'([NS])\s+(\d+)\s+(\d+)\s+(\d+\.?\d*).*?([EW])\s+(\d+)\s+(\d+)\s+(\d+\.?\d*)', line)
            if c_match:
                lat_dec = dms_to_decimal(c_match.group(1), c_match.group(2), c_match.group(3), c_match.group(4))
                lon_dec = dms_to_decimal(c_match.group(5), c_match.group(6), c_match.group(7), c_match.group(8))
            
            stations[callsign] = {'freq': freq_val, 'service': type_label, 'lat': lat_dec, 'lon': lon_dec}
        return stations
    except: return {}