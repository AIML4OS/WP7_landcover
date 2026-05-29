from __future__ import annotations

import json
from collections import defaultdict

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.errors import WindowError
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import box
from tqdm import tqdm
from rasterio.windows import Window

from landcover_pipeline.storage.path import raster_output_dir
from landcover_pipeline.storage.s3 import get_bucket


def _clip_geom_to_raster_bounds(geom, ds):
    """
    Clip geometry to raster bounds to avoid oversized windows.
    """
    if geom is None:
        return None

    if not geom.is_valid:
        geom = geom.buffer(0)

    if geom.is_empty:
        return None

    clipped = geom.intersection(box(*ds.bounds))
    if clipped.is_empty:
        return None

    return clipped


def _iter_chunk_windows(win, chunk_size: int):
    """
    Yield integer sub-windows covering the input window.
    """
    base = win.round_offsets().round_lengths()
    row_off = int(base.row_off)
    col_off = int(base.col_off)
    height = int(base.height)
    width = int(base.width)

    for row in range(row_off, row_off + height, chunk_size):
        chunk_height = min(chunk_size, row_off + height - row)
        for col in range(col_off, col_off + width, chunk_size):
            chunk_width = min(chunk_size, col_off + width - col)
            yield Window(col_off=col, row_off=row, width=chunk_width, height=chunk_height)


def _count_pixels_in_geom_chunked(ds, geom, n_intersections: int, chunk_size: int = 2048) -> dict[int, float]:
    """
    Count pixels inside a geometry by scanning the geometry window in chunks.
    """
    geom = _clip_geom_to_raster_bounds(geom, ds)
    if geom is None:
        return {}

    try:
        win = geometry_window(ds, [geom])
    except WindowError:
        return {}

    local_counts = defaultdict(float)

    for chunk_win in _iter_chunk_windows(win, chunk_size=chunk_size):
        arr = ds.read(1, window=chunk_win)

        mask = geometry_mask(
            [geom],
            out_shape=arr.shape,
            transform=ds.window_transform(chunk_win),
            invert=True,
            all_touched=False,
        )

        data = arr[mask]

        if ds.nodata is not None:
            data = data[data != ds.nodata]

        if data.size == 0:
            continue

        counts = np.bincount(data.astype(np.int64))
        weighted = counts * (1.0 / n_intersections)

        for cls, val in enumerate(weighted):
            if val > 0:
                local_counts[cls] += float(val)

    return dict(local_counts)


def compute_weighted_counts_low_memory(
    project_id: str,
    overlap_gpkg: str,
) -> dict[int, float]:
    """
    Low-memory raster counting path.

    It clips each geometry to the current raster bounds and skips
    invalid/out-of-raster windows before building the mask.
    """
    cells = gpd.read_file(overlap_gpkg)

    if cells.empty:
        raise ValueError("Overlap cells vuoto")

    cells["files_list"] = cells["files_json"].apply(
        lambda x: json.loads(x) if x else []
    )
    cells["n"] = cells["files_list"].apply(len)

    raster_map = defaultdict(list)

    for _, row in tqdm(
        cells.iterrows(),
        total=len(cells),
        desc="Building raster index",
        unit="cell",
    ):
        geom = row.geometry
        n = row["n"]

        if n == 0:
            continue

        for fr in row["files_list"]:
            raster_map[fr].append((geom, n))

    bucket = get_bucket()
    prefix = raster_output_dir(project_id)
    global_counts = defaultdict(float)

    for fr, geom_list in tqdm(
        raster_map.items(),
        total=len(raster_map),
        desc="Processing rasters",
        unit="raster",
    ):
        s3_path = f"/vsis3/{bucket}/{prefix}/{fr}"

        with rasterio.open(s3_path) as ds:
            for geom, n_intersections in tqdm(
                geom_list,
                desc=f"Counting in {fr}",
                leave=False,
                unit="geom",
            ):
                partial_counts = _count_pixels_in_geom_chunked(
                    ds,
                    geom,
                    n_intersections,
                )
                for cls, val in partial_counts.items():
                    global_counts[cls] += val

    return dict(global_counts)
