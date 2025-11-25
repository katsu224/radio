import re

# ================= CONFIGURACIÓN =================
LIMITE_PRUEBA = 5 
CARPETA_LOGOS = "logos_emisoras_final"

# URLs
URL_FCC_FM = "https://transition.fcc.gov/fcc-bin/fmq?state=&call=&city=&arn=&serv=FM&vac=&freq=0.0&fre2=107.9&facid=&class=&dkt=&list=2"
URL_FCC_AM = "https://transition.fcc.gov/fcc-bin/amq?state=&call=&city=&arn=&serv=AM&vac=&freq=530&fre2=1700&facid=&class=&dkt=&list=2"
URL_RADIO_BROWSER = "https://de1.api.radio-browser.info/json/stations/bycountry/United States of America"
URL_ORB_SEARCH = "https://onlineradiobox.com/search?q={}&c=us"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Regex precompilados
REGEX_CALLSIGN = re.compile(r'\b([KW][A-Z0-9-]{2,4})\b', re.IGNORECASE)
REGEX_FREQ_TITLE = re.compile(r'\b(\d{2,4}(\.\d)?)\b')
REGEX_ZIPCODE = re.compile(r'\b\d{5}(?:-\d{4})?\b')