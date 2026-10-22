"""Minimapas e conversão de coordenada de jogo para a imagem, com metadados públicos de mapas da valorant-api.com.

A imagem, constantes e listas são lidas localmente de data/maps/. Atualização
remota exige executar explicitamente ``python -m valorant.data.metadata --download``. Estes são
metadados atuais, sem associação garantida à versão histórica da partida.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from valorant.data.download import atomic_write_json, fetch

from valorant.paths import DATA_DIR

MAPS_DIR = DATA_DIR / "maps"
MAPS_METADATA_URL = "https://valorant-api.com/v1/maps"


def _read_metadata(name):
    metadata_file = MAPS_DIR / name
    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Metadados ausentes: {metadata_file}. Execute explicitamente: python -m valorant.data.metadata --download"
        )
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    if not isinstance(payload.get("data"), list):
        raise ValueError(f"Metadados inválidos: {metadata_file}")
    return payload["data"]


def load_maps_by_url():
    """Metadados indexados por mapUrl, que é o matchInfo.mapId dos JSONs."""
    all_maps = _read_metadata("maps.json")
    return {map_meta["mapUrl"]: map_meta for map_meta in all_maps}


def minimap_file(map_meta):
    image_file = MAPS_DIR / f"{map_meta['displayName']}.png"
    if not image_file.exists():
        raise FileNotFoundError(
            f"Minimapa ausente: {image_file}. Execute explicitamente: python -m valorant.data.metadata --download"
        )
    return image_file


def game_to_image_fraction(game_x, game_y, map_meta):
    """Fórmula da documentação da Riot: o y do jogo vira o x da imagem e o x do jogo vira o y, em fração 0..1."""
    image_x = game_y * map_meta["xMultiplier"] + map_meta["xScalarToAdd"]
    image_y = game_x * map_meta["yMultiplier"] + map_meta["yScalarToAdd"]
    return image_x, image_y


def callout_name(callout):
    return f'{callout["superRegionName"]} {callout["regionName"]}'


def nearest_callout(game_x, game_y, map_meta):
    """Nome da região (callout) mais próxima do ponto, por distância em coordenadas de jogo."""
    callouts = map_meta.get("callouts") or []
    if not callouts:
        return "?"
    closest = min(
        callouts,
        key=lambda callout: (callout["location"]["x"] - game_x) ** 2
        + (callout["location"]["y"] - game_y) ** 2,
    )
    return callout_name(closest)


def super_region(game_x, game_y, map_meta):
    """Só a parte grande do callout (A, B, C, Mid...), para saber em que área cada aliado está."""
    callouts = map_meta.get("callouts") or []
    if not callouts:
        return "?"
    closest = min(
        callouts,
        key=lambda callout: (callout["location"]["x"] - game_x) ** 2
        + (callout["location"]["y"] - game_y) ** 2,
    )
    return closest["superRegionName"]


def download_metadata(target_dir=MAPS_DIR):
    """Atualização explícita dos metadados atuais; não identifica a versão histórica do jogo."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    urls = {
        "maps.json": MAPS_METADATA_URL,
    }
    origins = {}
    for name, url in urls.items():
        payload = json.loads(fetch(url))
        if not isinstance(payload.get("data"), list):
            raise ValueError(f"Resposta inválida em {url}")
        atomic_write_json(target / name, payload)
        origins[f"maps/{name}"] = {
            "origin": url,
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    for meta in json.loads((target / "maps.json").read_text(encoding="utf-8"))["data"]:
        if meta.get("displayIcon"):
            image_file = target / f"{meta['displayName']}.png"
            if not image_file.exists():
                raw = fetch(meta["displayIcon"])
                from io import BytesIO
                from PIL import Image

                Image.open(BytesIO(raw)).verify()
                temporary = image_file.with_suffix(".png.tmp")
                temporary.write_bytes(raw)
                temporary.replace(image_file)
    from valorant.data.quality import write_manifest

    write_manifest(target.parent.parent / "data-manifest.json", target.parent, origins)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Baixar/atualizar metadados e minimapas explicitamente",
    )
    if parser.parse_args().download:
        download_metadata()
