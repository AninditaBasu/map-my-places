import csv
import json
import os
import time
from datetime import datetime

import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
from geopy.geocoders import Nominatim
import contextily as cx

# Timestamp
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

# Variables
INPUT_FILE = input(f"Enter the path to the CSV file, for example, C:\\maps\\pin-dot.csv: ")
CACHE_FILE = "geocode_cache.json"
OUTPUT_FILE = f"pin-dot-{timestamp}.png"

# Padding around computed bounds
PADDING = 0.08

# Web Mercator full-world bounds
WORLD_BOUNDS = (-20037508, -20037508, 20037508, 20037508)

# Natural Earth (remote)
WORLD_URL = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"

# Optional local cache for country geometries
WORLD_CACHE = "world_countries.geojson"

# -----------------------------
# Load CSV
# -----------------------------
print("Loading places...")

places = []

with open(INPUT_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        places.append({
            "name": row["place_name"].strip(),
            "country": row["place_country"].strip(),
            "lat": row["lat"].strip(),
            "lon": row["lon"].strip()
        })

print(f"{len(places)} places loaded.")

# -----------------------------
# Load geocode cache
# -----------------------------
print("Loading geocode cache...")

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE) as f:
        cache = json.load(f)
else:
    cache = {}

# -----------------------------
# Geocoding
# -----------------------------
print("Geocoding locations...")

geolocator = Nominatim(user_agent="terrain_mapper", timeout=10)

coords = []

for i, p in enumerate(places, start=1):

    name = p["name"]
    country = p["country"]

    print(f"  [{i}/{len(places)}] {name}, {country}")

    lat, lon = None, None

    # Try lat/lon first
    if p["lat"] and p["lon"]:
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except ValueError:
            print("    Invalid coordinates, falling back to geocoding...")

    # Geocode if needed
    if lat is None or lon is None:

        key = f"{name},{country}"

        if key in cache:
            lat, lon = cache[key]
        else:
            query = f"{name}, {country}"
            location = None

            for _ in range(3):
                try:
                    location = geolocator.geocode(query)
                    if location:
                        break
                except Exception:
                    time.sleep(2)

            if not location:
                print("    Not found:", query)
                continue

            lat, lon = location.latitude, location.longitude
            cache[key] = [lat, lon]

            time.sleep(1.1)

    coords.append({
        "name": name,
        "country": country,
        "lat": lat,
        "lon": lon
    })

print(f"{len(coords)} locations ready.")

# Save cache
print("Saving geocode cache...")

with open(CACHE_FILE, "w") as f:
    json.dump(cache, f, indent=2)

# -----------------------------
# Create GeoDataFrame (points)
# -----------------------------
print("Preparing point data...")

geometry = [Point(p["lon"], p["lat"]) for p in coords]

gdf = gpd.GeoDataFrame(coords, geometry=geometry, crs="EPSG:4326")
gdf_web = gdf.to_crs(epsg=3857)

# -----------------------------
# Load country geometries (remote or cached)
# -----------------------------
print("Loading country geometries...")

try:
    if os.path.exists(WORLD_CACHE):
        print("  Using cached data...")
        world = gpd.read_file(WORLD_CACHE)
    else:
        print("  Downloading from Natural Earth...")
        world = gpd.read_file(WORLD_URL)
        world.to_file(WORLD_CACHE, driver="GeoJSON")

    countries = set(p["country"] for p in coords)
    world_filtered = world[world["ADMIN"].isin(countries)]
    world_web = world_filtered.to_crs(epsg=3857)

except Exception as e:
    print("  Failed to load country data:", e)
    world_filtered = None

# -----------------------------
# Compute bounds
# -----------------------------
print("Computing map extent...")

if world_filtered is not None and not world_filtered.empty:

    xmin, ymin, xmax, ymax = world_web.total_bounds

    width = xmax - xmin
    world_width = WORLD_BOUNDS[2] - WORLD_BOUNDS[0]

    # If coverage is very large, use full world
    if width > 0.6 * world_width:
        print("  Using full world extent.")
        xmin, ymin, xmax, ymax = WORLD_BOUNDS

else:
    print("  Falling back to point bounds.")
    xmin, ymin, xmax, ymax = gdf_web.total_bounds

# Apply padding
width = xmax - xmin
height = ymax - ymin

xmin -= width * PADDING
xmax += width * PADDING
ymin -= height * PADDING
ymax += height * PADDING

# -----------------------------
# Plot the map
# -----------------------------
print("Rendering map...")

fig, ax = plt.subplots(figsize=(10, 10))

ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)

# Basemap (terrain only)
cx.add_basemap(
    ax,
    source=cx.providers.Esri.WorldPhysical,
    attribution=False
)

# Plot points
gdf_web.plot(
    ax=ax,
    color="#d62828",
    edgecolor="white",
    linewidth=0.6,
    markersize=35,
    zorder=5
)

ax.set_axis_off()

# -----------------------------
# Save output
# -----------------------------
print("Saving map image...")

plt.savefig(
    OUTPUT_FILE,
    dpi=300,
    bbox_inches="tight",
    facecolor="white"
)

plt.close()

print(f"{OUTPUT_FILE} generated.")

"""

C:\anindita\python_experiments\plot-map\data\example_country.csv
C:\anindita\python_experiments\plot-map\data\example_world.csv

"""