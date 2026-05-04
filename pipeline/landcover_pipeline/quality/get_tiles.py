from typing import List, Set
from pathlib import Path

import geopandas as gpd
import rasterio
from shapely.geometry import box
import os

from landcover_pipeline.storage.s3 import list_objects,get_bucket
from landcover_pipeline.storage.path import raster_output_dir,imagery_dir




def tiles_containing_points(
    points_file: Path,
    project_id: str,
) -> List[str]:
    """
    Given a point geometry file, return the list of raster tile IDs
    whose spatial extent contains at least one point.

    Raster metadata are read directly from S3 (no file download).
    """
    bucket=get_bucket()
    # 1. Read points
    gdf = gpd.read_file(points_file)
    if gdf.empty:
        return []

    # Ensure geometry is valid
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.is_valid]

    # 2. List raster tiles on S3
    raster_prefix = imagery_dir(project_id)
    
    raster_keys = list_objects(bucket=bucket, prefix=raster_prefix)
    
    matched_tiles: Set[str] = set()

    for key in raster_keys:
        if not key.lower().endswith(".tif"):
            continue

        tile_id = Path(key).stem

        # 3. Open raster metadata via GDAL / rasterio (no download)
        
        s3_path = f"/vsis3/{bucket}/{key}"

        if True:            
            with rasterio.open(s3_path) as ds:                
                raster_crs = ds.crs
                bounds = ds.bounds
                raster_bbox = box(bounds.left, bounds.bottom, bounds.right, bounds.top)

            # 4. Reproject points if needed
            points = gdf
            if points.crs != raster_crs:
                points = points.to_crs(raster_crs)

            # 5. Check spatial intersection
            if points.intersects(raster_bbox).any():
                matched_tiles.add(tile_id)
                print("match",key)

        #except Exception as e:
        #    print(f"⚠ Unable to read metadata for {tile_id}: {e}")

    return sorted(matched_tiles)

