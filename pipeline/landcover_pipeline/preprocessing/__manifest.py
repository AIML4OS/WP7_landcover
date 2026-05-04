# preprocessing/manifest.py

import json
from pathlib import Path
from datetime import datetime
from typing import Dict


def init_manifest(manifest_path: Path, header: Dict) -> None:
    """
    Initialize (or reset) a JSON manifest with a header entry.
    """
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "header",
            "created_at": str(datetime.now()),
            **header,
        }) + "\n")


def append_to_manifest(manifest_path: Path, entry: Dict) -> None:
    """
    Append a single entry to the JSON manifest.
    """
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "img",
            "timestamp": str( datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            **entry,
        }) + "\n")
