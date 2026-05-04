"""
Input scanning utilities for the Land Cover Pipeline.

This module is responsible for discovering raster input files
in a local directory. No processing or conversion is performed here.
"""

from pathlib import Path
from typing import List, Dict


SUPPORTED_EXTENSIONS = {".tif", ".tiff", ".ecw"}


def scan_input_directory(input_dir: str) -> List[Path]:
    """
    Scan a directory recursively and return supported raster files.

    Parameters
    ----------
    input_dir : str
        Root directory containing orthophotos.

    Returns
    -------
    List[Path]
        List of raster file paths.
    """
    root = Path(input_dir)

    if not root.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not root.is_dir():
        raise ValueError(f"Input path is not a directory: {input_dir}")

    files = [
        p for p in root.rglob("*")
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        raise ValueError("No supported raster files found in input directory")

    return sorted(files)


def describe_inputs(files: List[Path]) -> List[Dict]:
    """
    Build a minimal description of input files.

    Parameters
    ----------
    files : List[Path]

    Returns
    -------
    List[Dict]
        One dict per file, with basic metadata.
    """
    return [
        {
            "filename": f.name,
            "path": str(f),
            "extension": f.suffix.lower(),
            "size_bytes": f.stat().st_size,
        }
        for f in files
    ]
