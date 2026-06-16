from __future__ import annotations

import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.windows import Window
from tqdm import tqdm
from landcover_pipeline.storage.path import (
    footprint_path,
    imagery_dir,
    quality_work_dir,
)
from landcover_pipeline.storage.s3 import (
    download_file,
    get_bucket,
    upload_file,
)


def _normalize_tile_id(tile_value: object) -> str:
    name = Path(str(tile_value)).stem
    if name.endswith("_lc"):
        name = name[:-3]
    return name


def _load_lucas_points_in_aoi(lucas_csv: Path, aoi_path: Path) -> gpd.GeoDataFrame:
    lucas = pd.read_csv(lucas_csv,sep="[,;]")
    aoi = gpd.read_file(aoi_path)

    for c in ["POINT_NUTS0", "POINT_NUTS1", "POINT_NUTS2", "POINT_NUTS3"]:
        if c in lucas.columns:
            lucas[c] = lucas[c].astype(str).str.strip()

    lucas = lucas.dropna(subset=["POINT_LONG", "POINT_LAT"]).copy()

    points = gpd.GeoDataFrame(
        lucas,
        geometry=gpd.points_from_xy(lucas["POINT_LONG"], lucas["POINT_LAT"]),
        crs="EPSG:4326",
    )

    if points.crs != aoi.crs:
        points = points.to_crs(aoi.crs)

    aoi = aoi[["geometry"]].copy()
    points = gpd.sjoin(points, aoi, how="inner", predicate="intersects").drop(
        columns=["index_right"]
    )
    return points


def run_tiles_crop(
    project_id: str,
    lucas_csv: Path | str,
    aoi_path: Path | str,
    crop_size: int = 600,
) -> dict:
    if crop_size <= 0:
        raise ValueError("crop_size must be > 0")

    project = project_id.strip("/")
    lucas_csv = Path(lucas_csv)
    aoi_path = Path(aoi_path)

    bucket = get_bucket()
    s3_work_dir = quality_work_dir(project)
    imagery_prefix = imagery_dir(project)
    s3_crop_dir = f"{s3_work_dir}/tile_crops/{crop_size}"
    half = crop_size // 2

    with tempfile.TemporaryDirectory(prefix="quality_crop_") as tmpdir:
        tmpdir = Path(tmpdir)
        local_footprint = tmpdir / "footprint.gpkg"
        local_table_csv = tmpdir / "quality_points_to_tiles.csv"
        local_crop_dir = tmpdir / "tile_crops" / str(crop_size)
        local_crop_dir.mkdir(parents=True, exist_ok=True)

        download_file(
            bucket=bucket,
            s3_path=footprint_path(project),
            local_path=str(local_footprint),
        )
        footprints = gpd.read_file(local_footprint)

        points = _load_lucas_points_in_aoi(lucas_csv, aoi_path)
        if points.crs != footprints.crs:
            points = points.to_crs(footprints.crs)

        joined = gpd.sjoin(
            points,
            footprints[["tile", "geometry"]],
            how="left",
            predicate="intersects",
        )

        table = joined.copy()
        table["tile_id"] = table["tile"].map(
            lambda v: _normalize_tile_id(v) if pd.notna(v) else ""
        )
        table["has_tile"] = table["tile_id"].astype(str).str.len() > 0

        table_cols = ["POINT_ID", "POINT_NUTS0", "POINT_NUTS2", "SURVEY_LC1", "tile_id", "has_tile"]
        table = table[[c for c in table_cols if c in table.columns]].copy()
        table.to_csv(local_table_csv, index=False)
        s3_table_key = f"{s3_work_dir}/quality_points_to_tiles.csv"
        upload_file(
            local_path=str(local_table_csv),
            bucket=bucket,
            s3_path=s3_table_key,
        )

        valid_points = joined.dropna(subset=["tile"]).copy()
        valid_points["tile_id"] = valid_points["tile"].map(_normalize_tile_id)

        saved = 0
        processed_tiles = 0
        missing_tiles: list[str] = []
        
        for tile_id, points_on_tile in tqdm( valid_points.groupby("tile_id")):

            s3_tile_key = f"{imagery_prefix}{tile_id}.tif"
            local_tile = tmpdir / f"{tile_id}.tif"

            try:
                download_file(
                    bucket=bucket,
                    s3_path=s3_tile_key,
                    local_path=str(local_tile),
                )
            except Exception:
                missing_tiles.append(s3_tile_key)
                continue

            try:
                with rasterio.open(local_tile) as src:
                    for row in points_on_tile.itertuples(index=False):
                        r, col = src.index(row.geometry.x, row.geometry.y)
                        window = Window(
                            col_off=col - half,
                            row_off=r - half,
                            width=crop_size,
                            height=crop_size,
                        )
                        data = src.read(window=window, boundless=True, fill_value=0)
                        transform = src.window_transform(window)

                        profile = src.profile.copy()
                        profile.update(
                            {
                                "height": crop_size,
                                "width": crop_size,
                                "transform": transform,
                            }
                        )

                        point_id = str(row.POINT_ID)
                        out_path = local_crop_dir / f"{point_id}_{tile_id}.tif"
                        with rasterio.open(out_path, "w", **profile) as dst:
                            dst.write(data)

                        upload_file(
                            local_path=str(out_path),
                            bucket=bucket,
                            s3_path=f"{s3_crop_dir}/{out_path.name}",
                        )
                        out_path.unlink(missing_ok=True)
                        saved += 1
                processed_tiles += 1
            finally:
                local_tile.unlink(missing_ok=True)

    return {
        "project": project,
        "s3_work_dir": s3_work_dir,
        "s3_crop_dir": s3_crop_dir,
        "s3_table_key": s3_table_key,
        "points_total": int(len(points)),
        "valid_point_tile_pairs": int(len(valid_points)),
        "tiles_processed": int(processed_tiles),
        "crops_uploaded": int(saved),
        "missing_tiles": sorted(set(missing_tiles)),
    }
