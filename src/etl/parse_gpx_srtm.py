import argparse
import gpxpy
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import math
import os
import time
import json
import requests
import srtm
from pathlib import Path

CACHE_FILE = "data_raw/geocode_cache.json"
PHOTON_URL = "https://photon.komoot.io/reverse"
HEADERS = {"User-Agent": "ViaPodiensisProject/1.0"}


# -----------------------------
# Haversine
# -----------------------------
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# -----------------------------
# Lecture GPX
# -----------------------------
def parse_gpx(path):
    with open(path, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                points.append({"lon": p.longitude, "lat": p.latitude, "time": p.time})

    return pd.DataFrame(points)


# -----------------------------
# Altitude SRTM
# -----------------------------
def add_srtm_elevation(df):
    elevation_data = srtm.get_data()

    def get_srtm(lat, lon):
        elev = elevation_data.get_elevation(lat, lon)
        return float(elev) if elev is not None else None

    df["elevation"] = df.apply(lambda r: get_srtm(r["lat"], r["lon"]), axis=1)
    df["elevation"] = pd.to_numeric(df["elevation"], errors="coerce")
    df["elevation"] = df["elevation"].ffill().bfill()
    return df


# -----------------------------
# Cache disque
# -----------------------------
def load_cache(path=CACHE_FILE):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache, path=CACHE_FILE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# -----------------------------
# Appel Nominatim via Photon (Komoot)
# -----------------------------

def _nominatim_call(session, lat, lon, verbose=False):
    params = {"lat": lat, "lon": lon, "lang": "fr"}

    for attempt in range(3):
        try:
            r = session.get(PHOTON_URL, params=params, headers=HEADERS, timeout=15)

            if r.status_code != 200:
                print(f"  [WARN] HTTP {r.status_code} pour ({lat}, {lon})")
                time.sleep(2 ** attempt)
                continue

            data = r.json()
            features = data.get("features", [])
            if not features:
                return "Lieu inconnu"

            props = features[0].get("properties", {})

            # Photon retourne : name, city, town, village, county, state
            place = (
                props.get("name")
                or props.get("village")
                or props.get("town")
                or props.get("city")
                or props.get("county")
                or props.get("state")
                or "Lieu inconnu"
            )

            if verbose:
                print(f"  [OK] ({lat:.3f}, {lon:.3f}) → {place}")

            return place

        except requests.exceptions.Timeout:
            print(f"  [WARN] Timeout tentative {attempt+1}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  [ERROR] ({lat}, {lon}): {e}")
            time.sleep(2 ** attempt)

    return "Lieu inconnu"

# -----------------------------
# Reverse geocoding optimisé
# -----------------------------
def add_place_names(df, min_dist_m=500, cache_file=CACHE_FILE, verbose=True):
    """
    Géocode 1 point tous les `min_dist_m` mètres, propage par ffill.
    Cache persisté sur disque. Affiche progression et stats.
    """
    # Calcul de la distance cumulée si elle n'existe pas encore
    if "distance_m" not in df.columns:
        distances = [0.0]
        cumdist = 0.0
        for i in range(1, len(df)):
            d = haversine(df.loc[i - 1, "lon"], df.loc[i - 1, "lat"],
                          df.loc[i, "lon"], df.loc[i, "lat"])
            cumdist += d
            distances.append(cumdist)
        df["distance_m"] = distances

    cache = load_cache(cache_file)
    session = requests.Session()

    # Identifier les jalons spatiaux à géocoder
    to_geocode = []
    last_dist = -min_dist_m
    for i in df.index:
        if df.loc[i, "distance_m"] - last_dist >= min_dist_m:
            to_geocode.append(i)
            last_dist = df.loc[i, "distance_m"]

    total = len(to_geocode)
    estimated_min = total / 60
    print(f"Points GPX       : {len(df):,}")
    print(f"Jalons à géocoder: {total:,}  (~{estimated_min:.0f} min)")
    print(f"Cache existant   : {len(cache)} entrées")

    # Géocoder les jalons manquants
    place_at_index = {}
    new_calls = 0

    for idx, i in enumerate(to_geocode):
        lat = round(df.loc[i, "lat"], 3)
        lon = round(df.loc[i, "lon"], 3)
        key = f"{lat},{lon}"

        if key in cache:
            place_at_index[i] = cache[key]
        else:
            place = _nominatim_call(session, lat, lon, verbose=verbose)
            cache[key] = place
            place_at_index[i] = place
            new_calls += 1
            time.sleep(1)  # politique Nominatim : max 1 req/s

            # Sauvegarde intermédiaire toutes les 50 nouvelles entrées
            if new_calls % 50 == 0:
                save_cache(cache, cache_file)
                print(f"  → Cache sauvegardé ({new_calls} nouveaux appels, {idx+1}/{total})")

    save_cache(cache, cache_file)
    print(f"Terminé : {new_calls} nouveaux appels, {total - new_calls} depuis le cache.")

    # Construire la série sparse puis propager
    sparse = pd.Series(index=df.index, dtype="object")
    for i, place in place_at_index.items():
        sparse.iloc[df.index.get_loc(i)] = place

    df["place_name"] = sparse.ffill().bfill()

    # Vérification rapide
    n_inconnu = (df["place_name"] == "Lieu inconnu").sum()
    print(f"Lieu inconnu     : {n_inconnu}/{len(df)} points ({100*n_inconnu/len(df):.1f}%)")
    if n_inconnu == len(df):
        print("  ⚠️  Tous les appels ont échoué — vérifiez la connectivité réseau et le User-Agent.")

    return df


# -----------------------------
# Calcul du profil
# -----------------------------
def compute_profile(df):
    df = df.reset_index(drop=True)

    distances = [0.0]
    cumdist = 0.0
    for i in range(1, len(df)):
        d = haversine(df.loc[i - 1, "lon"], df.loc[i - 1, "lat"],
                      df.loc[i, "lon"], df.loc[i, "lat"])
        cumdist += d
        distances.append(cumdist)

    df["distance_m"] = distances

    df["elevation_diff"] = df["elevation"].diff().fillna(0.0)
    df["elevation_diff"] = df["elevation_diff"].replace([float("inf"), float("-inf")], 0.0)
    df["slope"] = df["elevation_diff"] / df["distance_m"].diff().replace(0, pd.NA)

    return df


# -----------------------------
# Export
# -----------------------------
def export_outputs(df, out_geo, out_profile):
    coords = list(zip(df["lon"], df["lat"]))
    line = LineString(coords)
    gdf_line = gpd.GeoDataFrame(
        {"name": ["via-podiensis-full-route-srtm"]},
        geometry=[line],
        crs="EPSG:4326",
    )

    os.makedirs(os.path.dirname(out_geo), exist_ok=True)
    gdf_line.to_file(out_geo, driver="GeoJSON")

    os.makedirs(os.path.dirname(out_profile), exist_ok=True)
    df.to_csv(out_profile, index=False)


# -----------------------------
# Main
# -----------------------------
def main(args):
    df = parse_gpx(args.input)
    if df.empty:
        raise SystemExit("Aucun point trouvé dans le GPX.")

    df = add_srtm_elevation(df)
    df = add_place_names(df, min_dist_m=args.min_dist, cache_file=args.cache, verbose=args.verbose)
    df = compute_profile(df)

    export_outputs(df, args.out_geo, args.out_profile)

    print(f"Exporté GeoJSON : {args.out_geo}")
    print(f"Exporté CSV     : {args.out_profile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse GPX + SRTM + Reverse Geocoding")
    parser.add_argument("--input", required=True, help="Fichier GPX source")
    parser.add_argument("--out_geo", default="data_raw/route_srtm.geojson")
    parser.add_argument("--out_profile", default="data_raw/profile_srtm.csv")
    parser.add_argument("--min_dist", type=float, default=500,
                        help="Distance minimale entre deux appels API (mètres, défaut: 500)")
    parser.add_argument("--cache", default=CACHE_FILE,
                        help="Chemin du fichier cache JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Afficher chaque appel Nominatim")
    args = parser.parse_args()
    main(args)
