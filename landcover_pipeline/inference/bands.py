# inference/bands.py
"""
Which bands a model reads from a stored tile.

Imagery is stored by content (<tile>_RGB.tif: R,G,B / <tile>_RGBI.tif: R,G,B,IR).
The execution (--run) decides how a tile is read. The bands come from the
part of the run name before the first "_"; the rest is a free label that keeps
executions apart (rgb_swin, rgb_convnext, irg_convnext ...):

    rgb... : bands R,G,B        -> channels [1,2,3]  (tiles _RGB and _RGBI)
    irg... : bands IR,R,G       -> channels [4,1,2]  (tiles _RGBI only)

Without a run (plain project id) the tile name decides, as before:
legacy tiles <tile>_RGB / <tile>_IRG (3-band IR,R,G file).
"""
from pathlib import Path
from typing import List, Optional, Tuple

from landcover_pipeline.storage.path import run_name

RUN_CHANNELS = {"RGB": [1, 2, 3], "IRG": [4, 1, 2]}


def tile_content(tile_id: str) -> Optional[str]:
    """RGB, RGBI or IRG (legacy) token of the tile id, None if absent."""
    for token in Path(tile_id).stem.split("_"):
        if token in {"RGB", "RGBI", "IRG"}:
            return token
    return None


def run_bands(run: str) -> Optional[str]:
    """Bands of a run: RGB or IRG from the part before the first "_", else None."""
    return {"rgb": "RGB", "irg": "IRG"}.get(run.split("_")[0])


def validate_run(model: str, run: Optional[str]) -> None:
    """Rules on the run name; raises ValueError."""
    if run is None:
        return
    if model == "flairhub":
        if run_bands(run) is None:
            raise ValueError(
                "For flairhub --run must be rgb or irg, optionally followed by a "
                f"label (rgb_swin, irg_convnext ...), got {run!r}"
            )
    elif run_bands(run) == "IRG":
        raise ValueError(
            f"--run {run} is not supported with FLAIR-1 (small/large): "
            "it would need a channel override for the 4-band tiles"
        )


def resolve_bands(project_id: str, tile_id: str) -> Tuple[str, Optional[List[int]]]:
    """
    Returns (bands, channels): bands is "RGB" or "IRG"; channels is the
    channel selection to apply, or None to keep the one of the template.
    Raises ValueError when the tile cannot be read with the run.
    """
    content = tile_content(tile_id)
    run = run_name(project_id)

    if run is None:                                   # legacy: tile name decides
        if content in {"RGB", "IRG"}:
            return content, None
        if content == "RGBI":
            raise ValueError(
                f"Tile {tile_id} has 4 bands (RGBI): use --run rgb or --run irg"
            )
        raise ValueError(f"Unable to infer bands (RGB/IRG) from tile_id='{tile_id}'")

    bands = run_bands(run) or "RGB"                   # free names (FLAIR-1) read RGB
    if content is None:
        raise ValueError(f"Unable to infer content (RGB/RGBI) from tile_id='{tile_id}'")
    if content == "IRG":
        raise ValueError(
            f"Tile {tile_id} is a legacy IRG tile: process it without --run"
        )
    if bands == "IRG" and content != "RGBI":
        raise ValueError(f"Tile {tile_id} has no infrared band: run irg needs an RGBI tile")
    return bands, RUN_CHANNELS[bands]


def skip_reason(project_id: str, tile_id: str) -> Optional[str]:
    """Why the tile cannot be processed in this run, None if it can."""
    try:
        resolve_bands(project_id, tile_id)
    except ValueError as exc:
        return str(exc)
    return None
