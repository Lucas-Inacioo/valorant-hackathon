"""Caminhos comuns, sempre relativos à raiz deste repositório."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MANIFEST_PATH = PROJECT_ROOT / "data-manifest.json"
