"""Baixa os JSONs de partidas da pasta pública do Drive do hackathon para a pasta data/.

Uso: python download_data.py
"""
import html
import json
import os
import re
import tempfile
import urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT_FOLDER_ID = "1IuptLxv1FpcvrfB6a7z9bEqPNYSsQ-hW"
DATA_DIR = Path(__file__).parent / "data"
FOLDER_LISTING_URL = "https://drive.google.com/embeddedfolderview?id={}"
FILE_DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id={}"
PARALLEL_DOWNLOADS = 6
# Cada entrada da listagem é um link para arquivo ou subpasta seguido do nome em flip-entry-title
ENTRY_PATTERN = re.compile(r'href="https://drive\.google\.com/(file/d|drive/folders)/([-\w]+)[^"]*"[^>]*>.*?flip-entry-title">([^<]+)<', re.S)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def list_folder(folder_id):
    """Devolve o nome da pasta e a lista de (is_folder, id, nome) dos itens dela."""
    page = fetch(FOLDER_LISTING_URL.format(folder_id)).decode("utf-8")
    title = re.search(r"<title>([^<]*)</title>", page)
    if not title:
        raise ValueError(f"Listagem inválida da pasta {folder_id}")
    folder_name = html.unescape(title.group(1))
    entries = [(kind == "drive/folders", item_id, html.unescape(name)) for kind, item_id, name in ENTRY_PATTERN.findall(page)]
    return folder_name, entries


def atomic_write_json(target_path, payload):
    """Nunca deixa um JSON parcial no destino se a escrita falhar."""
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target_path.name}.", dir=target_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(target_path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _validate_match(raw, source):
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not all(key in payload for key in ("matchInfo", "roundResults", "players")):
        raise ValueError(f"JSON de partida inválido: {source}")
    if (not isinstance(payload["roundResults"], list) or not isinstance(payload["players"], list)
            or not isinstance(payload["matchInfo"], dict) or not payload["matchInfo"].get("matchId")):
        raise ValueError(f"Estrutura de partida inválida: {source}")
    return payload


def download_file(file_id, target_path):
    target_path = Path(target_path)
    url = FILE_DOWNLOAD_URL.format(file_id)
    # Um arquivo existente é aceito somente depois de validar seu conteúdo.
    if target_path.exists():
        try:
            _validate_match(target_path.read_bytes(), target_path)
            return {"path": target_path, "origin": url, "status": "existing_validated"}
        except (ValueError, UnicodeDecodeError):
            pass
    payload = _validate_match(fetch(url), url)
    atomic_write_json(target_path, payload)
    print(f"baixado: {target_path.name}")
    return {"path": target_path, "origin": url, "status": "downloaded",
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat()}


def _safe_name(name):
    if not name or name in {".", ".."} or Path(name).name != name or "\\" in name:
        raise ValueError(f"Nome remoto inválido: {name!r}")
    return name


def download_folder(folder_id, parent_dir, executor, futures=None):
    futures = [] if futures is None else futures
    folder_name, entries = list_folder(folder_id)
    folder_dir = parent_dir / _safe_name(folder_name)
    folder_dir.mkdir(parents=True, exist_ok=True)
    print(f"pasta: {folder_dir.name} ({len(entries)} itens)")
    for is_folder, item_id, item_name in entries:
        if is_folder:
            download_folder(item_id, folder_dir, executor, futures)
        else:
            if not item_name.lower().endswith(".json"):
                raise ValueError(f"Arquivo inesperado na base de partidas: {item_name}")
            futures.append(executor.submit(download_file, item_id, folder_dir / _safe_name(item_name)))
    return futures


def download_dataset(data_dir=DATA_DIR, manifest_path=None):
    target = Path(data_dir)
    target.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as executor:
        futures = []
        try:
            download_folder(ROOT_FOLDER_ID, target, executor, futures)
        except Exception as error:
            errors.append(f"Listagem: {type(error).__name__}: {error}")
        for future in as_completed(futures):
            try:
                records.append(future.result())
            except Exception as error:
                errors.append(f"{type(error).__name__}: {error}")
    if errors:
        raise RuntimeError(f"{len(errors)} download(s) falharam: " + "; ".join(errors))
    if manifest_path is not None:
        from data_quality import write_manifest
        origins = {str(record["path"].relative_to(target)):
                   {"origin": record["origin"], **({"downloaded_at_utc": record["downloaded_at_utc"]} if "downloaded_at_utc" in record else {})}
                   for record in records}
        write_manifest(manifest_path, target, origins)
    return records


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parent / "data-manifest.json")
    args = parser.parse_args()
    download_dataset(args.data_dir, args.manifest)


if __name__ == "__main__":
    main()
