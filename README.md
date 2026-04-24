# Via Podiensis Data Project

But: pipeline ETL pour la Via Podiensis (GR65) — ingestion GPX, profil d'altitude, export GeoJSON.

Structure:
- data_raw/: fichiers GPX et sorties
- src/etl/parse_gpx.py: script d'ingestion
- notebooks/: notebooks d'EDA et walkthrough
- app/: prototype de dashboard

### ✅ Phase 1 — ETL & ingestion (terminée)
- Parsing GPX (14 765 points, ~740 km)
- Altitude recalculée via SRTM (remplacement données GPX manquantes)
- Distance cumulée et profil (dénivelé, pente) calculés point par point
- Reverse geocoding via **Photon/Komoot** (366 appels, ~6 min)
  avec sous-échantillonnage spatial (1 appel/2 km) et cache JSON persisté
- Export GeoJSON (tracé) + CSV (profil complet)
- Notebook correctif pour les résidus "Lieu inconnu"

### ⏳ Phase 2 — Enrichissement POI & hébergements
### ⏳ Phase 3 — Analyses (profil d'effort, segmentation d'étapes)
### ⏳ Phase 4 — Dashboard interactif

## Fichiers clés
| Fichier | Description |
|---|---|
| `data_raw/profile_srtm.csv` | Dataset principal — 14 765 points, 8 colonnes |
| `data_raw/route_srtm.geojson` | Tracé GeoJSON EPSG:4326 |
| `src/etl/parse_gpx_srtm.py` | Script ETL CLI (`--input`, `--min_dist`, `--verbose`) |
| `notebooks/00_explore_gpx_ipyn.ipynb` | Exploration & ingestion |
| `notebooks/99_correct_place_names.ipynb` | Correction manuelle geocoding |


# Structure du projet
via-podiensis-project/
├── data_raw/
│   ├── via-podiensis-full-route.gpx     ← source brute
│   ├── profile_srtm.csv                 ← ✅ dataset enrichi (lat, lon, time,
│   │                                         elevation, distance_m, elevation_diff,
│   │                                         slope, place_name)
│   ├── route_srtm.geojson               ← ✅ tracé ligne pour SIG
│   ├── geocode_cache.json               ← ✅ cache Photon persisté
│   └── a_corriger.csv                   ← outil correctif temporaire
│
├── notebooks/
│   ├── 00_explore_gpx_ipyn.ipynb        ← ✅ exploration & ingestion (SRTM +
│   │                                         geocoding + profil + export)
│   └── 99_correct_place_names.ipynb     ← ✅ correction manuelle Lieu inconnu
│
├── src/
│   └── etl/
│       └── parse_gpx_srtm.py            ← ✅ script ETL CLI complet
│                                              (--input, --min_dist, --verbose, --cache)
│
├── app/
│   └── streamlit_app.py                 ← ⏳ dashboard interactif
│
├── requirements.txt
└── README.md
