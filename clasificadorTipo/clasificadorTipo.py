# ================= CLASIFICADOR DE TIPO =================
def classify_about_type(tags_str):
    """
    Clasificador avanzado para radios basado en pesos por palabra clave.
    Muy completo, escalable y de calidad profesional.
    """
    if not tags_str:
        return "Music"

    tags = tags_str.lower().replace(",", " ")

    categories = {
        # --- NEWS & TALK ---
        'News/Talk': {
            'news': 3, 'talk': 3, 'information': 3, 'public radio': 2,
            'politics': 2, 'debate': 2
        },
        'Business News': {
            'business': 3, 'economy': 3, 'finance': 2, 'market': 2
        },
        'Sports Talk': {
            'sport': 3, 'sports': 3, 'nfl': 2, 'nba': 2, 'mlb': 2,
            'hockey': 2, 'soccer': 2
        },

        # --- RELIGION ---
        'Christian': {
            'christian': 3, 'worship': 3, 'faith': 2, 'jesus': 2
        },
        'Catholic': {
            'catholic': 3, 'rosary': 2, 'mass': 2
        },
        'Gospel': {
            'gospel': 3, 'praise': 2
        },
        'Islamic': {
            'islam': 3, 'quran': 3, 'muslim': 2, 'al quran': 2
        },
        'Jewish': {
            'jewish': 3, 'hebrew': 2, 'torah': 2
        },
        'Hindu': {
            'hindu': 3, 'mantra': 2, 'bhajan': 2
        },

        # --- EDUCATION ---
        'Education': {
            'education': 3, 'learning': 2, 'university': 3,
            'college': 3, 'student': 2
        },

        # --- LATIN / REGIONAL ---
        'Latin': {
            'spanish': 3, 'latino': 3, 'reggaeton': 3, 'cumbia': 2,
            'salsa': 2, 'bachata': 2, 'merengue': 2, 'tropical': 2
        },
        'Brazil/Portuguese': {
            'brazil': 3, 'brasil': 3, 'portuguese': 3, 'forro': 2,
            'sertanejo': 2
        },
        'French': {
            'french': 3, 'francais': 3
        },
        'German': {
            'german': 3, 'deutsch': 3
        },
        'Italian': {
            'italian': 3, 'italiano': 3
        },
        'African': {
            'africa': 3, 'african': 3, 'afrobeat': 2
        },
        'Asian': {
            'asian': 3, 'japan': 2, 'korea': 2, 'china': 2,
            'kpop': 2, 'jpop': 2
        },

        # --- MUSIC GENRES ---
        'Pop': {'pop': 3, 'top 40': 3, 'hits': 2},
        'Rock': {'rock': 3, 'metal': 2, 'punk': 2},
        'Hip-Hop/Rap': {'rap': 3, 'hiphop': 3, 'hip hop': 3, 'trap': 2},
        'Electronic/Dance': {'edm': 3, 'electronic': 3, 'dance': 2, 'house': 2},
        'Classical': {'classical': 3, 'symphony': 2, 'orchestra': 2},
        'Jazz/Blues': {'jazz': 3, 'blues': 2, 'swing': 2},
        'Country': {'country': 3, 'americana': 2},
        'R&B/Soul': {'rnb': 3, 'soul': 3, 'funk': 2},

        # --- CULTURE ---
        'Comedy': {'comedy': 3, 'funny': 2},
        'Lifestyle': {'lifestyle': 3, 'fashion': 2},
        'Anime/Game': {'anime': 3, 'gaming': 3, 'game': 3, 'otaku': 2},
        'Culture/Arts': {'culture': 3, 'arts': 2},
        'Documentary': {'documentary': 3, 'history': 2},

        # --- WELLNESS ---
        'Meditation': {'meditation': 3, 'mantra': 2},
        'Relax': {'relax': 3, 'chill': 2},
        'Sleep': {'sleep': 3, 'calm': 2},
        'Wellness': {'wellness': 3, 'health': 2},

        # --- PUBLIC SAFETY / UTILITIES ---
        'Emergency': {'emergency': 3, 'alert': 2},
        'Traffic': {'traffic': 3, 'commute': 2},
        'Weather': {'weather': 3, 'storm': 2},
        'Police/Scanner': {'police': 3, 'scanner': 3, 'fire dept': 2},
    }

    scores = {cat: 0 for cat in categories}

    for cat, words in categories.items():
        for word, weight in words.items():
            if word in tags:
                scores[cat] += weight

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "Music"
    
    return best