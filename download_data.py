"""Baixa os JSONs de partidas da pasta pública do Drive do hackathon para a pasta data/.

Uso: python download_data.py
"""
import html
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
    folder_name = html.unescape(re.search(r"<title>([^<]*)</title>", page).group(1))
    entries = [(kind == "drive/folders", item_id, html.unescape(name)) for kind, item_id, name in ENTRY_PATTERN.findall(page)]
    return folder_name, entries


def download_file(file_id, target_path):
    if target_path.exists() and target_path.stat().st_size > 0:
        return
    target_path.write_bytes(fetch(FILE_DOWNLOAD_URL.format(file_id)))
    print(f"baixado: {target_path.relative_to(DATA_DIR)}")


def download_folder(folder_id, parent_dir, executor):
    folder_name, entries = list_folder(folder_id)
    folder_dir = parent_dir / folder_name
    folder_dir.mkdir(parents=True, exist_ok=True)
    print(f"pasta: {folder_dir.relative_to(DATA_DIR)} ({len(entries)} itens)")
    for is_folder, item_id, item_name in entries:
        if is_folder:
            download_folder(item_id, folder_dir, executor)
        else:
            executor.submit(download_file, item_id, folder_dir / item_name)


def main():
    with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as executor:
        download_folder(ROOT_FOLDER_ID, DATA_DIR, executor)


if __name__ == "__main__":
    main()
