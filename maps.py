"""Minimapas e conversão de coordenada de jogo para a imagem, com metadados públicos da valorant-api.com.

A imagem e as quatro constantes de cada mapa são baixadas uma vez para data/maps/. Não é dado de partida.
"""
import json
from pathlib import Path

from download_data import fetch

MAPS_DIR = Path(__file__).parent / "data" / "maps"
MAPS_METADATA_URL = "https://valorant-api.com/v1/maps"


def load_maps_by_url():
    """Metadados indexados por mapUrl, que é o matchInfo.mapId dos JSONs."""
    metadata_file = MAPS_DIR / "maps.json"
    if not metadata_file.exists():
        MAPS_DIR.mkdir(parents=True, exist_ok=True)
        metadata_file.write_bytes(fetch(MAPS_METADATA_URL))
    all_maps = json.loads(metadata_file.read_text(encoding="utf-8"))["data"]
    return {map_meta["mapUrl"]: map_meta for map_meta in all_maps}


def minimap_file(map_meta):
    image_file = MAPS_DIR / f"{map_meta['displayName']}.png"
    if not image_file.exists():
        image_file.write_bytes(fetch(map_meta["displayIcon"]))
    return image_file


def game_to_image_fraction(game_x, game_y, map_meta):
    """Fórmula da documentação da Riot: o y do jogo vira o x da imagem e o x do jogo vira o y, em fração 0..1."""
    image_x = game_y * map_meta["xMultiplier"] + map_meta["xScalarToAdd"]
    image_y = game_x * map_meta["yMultiplier"] + map_meta["yScalarToAdd"]
    return image_x, image_y
