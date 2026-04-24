# Via Podiensis Data Project

But: pipeline ETL pour la Via Podiensis (GR65) — ingestion GPX, profil d'altitude, export GeoJSON.

Structure:
- data_raw/: fichiers GPX et sorties
- src/etl/parse_gpx.py: script d'ingestion
- notebooks/: notebooks d'EDA et walkthrough
- app/: prototype de dashboard

### Phase 1 — ETL & ingestion
- Parsing GPX (14 765 points, ~740 km)
- Altitude recalculée via SRTM (remplacement données GPX manquantes)
- Distance cumulée et profil (dénivelé, pente) calculés point par point
- Reverse geocoding via **Photon/Komoot** (366 appels, ~6 min)
  avec sous-échantillonnage spatial (1 appel/2 km) et cache JSON persisté
- Export GeoJSON (tracé) + CSV (profil complet)
- Notebook correctif pour les résidus "Lieu inconnu"


### Phase 2 — Enrichissement POI & hébergements
Objectif : constituer une base de données exhaustive de l'offre d'accueil le long du GR65.
- **Source** : OpenStreetMap via l'API Overpass.
- **Filtres** : Catégories `tourism` (hostel, guest_house, hotel, camp_site, alpine_hut) et `amenity=shelter`.
- **Traitement Spatial** : Chaque établissement est projeté sur la trace GPS pour calculer son point kilométrique exact (`km_sur_trace`).
- **Sortie** : `data_raw/hebergements.csv`.

### Phase 3 — Analyse & Segmentation intelligente (`02_analysis.ipynb`)
Contrairement à un découpage mathématique linéaire, ce module simule un plan de marche réaliste.
- **Modèle de Segmentation** : L'algorithme cherche l'hébergement le plus proche de la cible (ex: 25 km) pour définir la fin d'une étape.
- **Indicateurs calculés** : Distance réelle, Dénivelé positif (D+), Profil altimétrique et score de difficulté par segment.
- **Sortie** : `outputs/itineraire_custom.csv`.

### Phase 4 — Dashboard interactif

## Fichiers clés
| Fichier | Description |
|---|---|
| `data_raw/profile_srtm.csv` | Dataset principal — 14 765 points, 8 colonnes |
| `data_raw/route_srtm.geojson` | Tracé GeoJSON EPSG:4326 |
| `src/etl/parse_gpx_srtm.py` | Script ETL CLI (`--input`, `--min_dist`, `--verbose`) |
| `notebooks/00_explore_gpx_ipyn.ipynb` | Exploration & ingestion |
| `notebooks/99_correct_place_names.ipynb` | Correction manuelle geocoding |
| `hebergements.csv` | Liste brute des POI (Nom, Type, Coordonnées, KM sur trace). |
| `itineraire_officiel.csv` | Statistiques basées sur les étapes historiques du GR65. |
| `itineraire_custom.csv` | Plan de marche généré dynamiquement selon la cadence choisie (ex: 25km/j). 

Chaque étape de l'itinéraire contient les champs : `etape`, `depart`, `arrivee`, `distance_km`, `d_plus_m`, et `difficulte`.

## Logique de Planification (Segmentation)

Le projet confronte deux visions de la marche :
1. **La Vision Théorique** : Découpage strict tous les X kilomètres.
2. **La Vision "Pèlerin" (Implémentée)** : Le chemin impose ses points d'arrêt. L'algorithme de segmentation personnalisée utilise la base `hebergements.csv` pour identifier les "villes-étapes" réelles, garantissant qu'une étape ne se termine jamais en pleine nature, mais là où une infrastructure existe.

> **Note technique** : Une marge de sécurité de 5 km est appliquée entre deux étapes pour éviter les micro-segments dans les zones à forte densité de gîtes.


## Structure du projet

```
via-podiensis-project/
├── data_raw/
│   ├── via-podiensis-full-route.gpx      ← source brute
│   ├── profile_srtm.csv                 ← dataset enrichi (altimétrie + géocodage)
│   ├── route_srtm.geojson               ← tracé ligne pour SIG
│   ├── hebergements.csv                 ← POI extraits d'Overpass (Notebook 01)
│   ├── geocode_cache.json               ← cache Photon persisté
│   └── a_corriger.csv                   ← outil correctif temporaire
│
├── notebooks/
│   ├── 00_explore_gpx.ipynb             ← exploration & ingestion (SRTM + Profil)
│   ├── 01_hebergements.ipynb            ← ETL Overpass API & spatial join (Hébergements)
│   ├── 02_analysis.ipynb                ← Segmentation intelligente & calcul d'étapes
│   └── 99_correct_place_names.ipynb     ← correction manuelle Lieu inconnu
│
├── outputs/
│   ├── itineraire_officiel.csv          ← stats sur les étapes historiques
│   └── itineraire_custom.csv            ← plan de marche basé sur les hébergements
│
├── src/
│   └── etl/
│       └── parse_gpx_srtm.py            ← script ETL CLI complet
│
├── app/
│   └── streamlit_app.py                 ← dashboard interactif
│
├── requirements.txt
└── README.md

```