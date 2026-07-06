from __future__ import annotations

import json
import math
import time
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "static" / "assets"
OUTPUT_IMAGE = OUTPUT_DIR / "denmark-map.png"
OUTPUT_META = OUTPUT_DIR / "denmark-map.json"

ZOOM = 8
TILE_SIZE = 256
OUTPUT_SIZE = (1400, 1050)
BOUNDS = {
    "lat_min": 54.25,
    "lon_min": 5.2,
    "lat_max": 58.05,
    "lon_max": 14.3,
}


def lon_to_pixel_x(lon: float, zoom: int) -> float:
    scale = TILE_SIZE * (2**zoom)
    return (lon + 180.0) / 360.0 * scale


def lat_to_pixel_y(lat: float, zoom: int) -> float:
    scale = TILE_SIZE * (2**zoom)
    lat_rad = math.radians(lat)
    return (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * scale


def fetch_tile(x: int, y: int, z: int) -> Image.Image:
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DykkeForhold/1.0 local static map builder",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return Image.open(BytesIO(response.read())).convert("RGB")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    left = lon_to_pixel_x(BOUNDS["lon_min"], ZOOM)
    right = lon_to_pixel_x(BOUNDS["lon_max"], ZOOM)
    top = lat_to_pixel_y(BOUNDS["lat_max"], ZOOM)
    bottom = lat_to_pixel_y(BOUNDS["lat_min"], ZOOM)

    tile_left = math.floor(left / TILE_SIZE)
    tile_right = math.floor((right - 1) / TILE_SIZE)
    tile_top = math.floor(top / TILE_SIZE)
    tile_bottom = math.floor((bottom - 1) / TILE_SIZE)

    mosaic = Image.new(
        "RGB",
        ((tile_right - tile_left + 1) * TILE_SIZE, (tile_bottom - tile_top + 1) * TILE_SIZE),
        "#d8eef1",
    )

    for x in range(tile_left, tile_right + 1):
        for y in range(tile_top, tile_bottom + 1):
            tile = fetch_tile(x, y, ZOOM)
            mosaic.paste(tile, ((x - tile_left) * TILE_SIZE, (y - tile_top) * TILE_SIZE))
            time.sleep(0.08)

    crop = (
        round(left - tile_left * TILE_SIZE),
        round(top - tile_top * TILE_SIZE),
        round(right - tile_left * TILE_SIZE),
        round(bottom - tile_top * TILE_SIZE),
    )
    image = mosaic.crop(crop).resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
    image.save(OUTPUT_IMAGE, optimize=True)

    OUTPUT_META.write_text(
        json.dumps(
            {
                "source": "OpenStreetMap raster tiles",
                "attribution": "© OpenStreetMap contributors",
                "zoom": ZOOM,
                "bounds": BOUNDS,
                "size": OUTPUT_SIZE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
