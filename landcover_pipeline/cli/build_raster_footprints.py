import argparse
import tempfile

import geopandas as gpd
import rasterio
from shapely.geometry import box
from tqdm import tqdm
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from landcover_pipeline.storage.path import footprint_path, raster_output_dir
from landcover_pipeline.storage.s3 import get_bucket, list_objects, upload_file

def build_tile_footprints(project_id: str) -> gpd.GeoDataFrame:
    """
    Costruisce i footprint leggendo solo i metadati dei raster su S3.
    """
    bucket = get_bucket()
    print(bucket)
    prefix = project_id
    #prefix = raster_output_dir(project_id)

    print("bucket: " + bucket)
    print("prefix: " + prefix)
    objects = list(list_objects(bucket, prefix, substring="lc"))
    keys = [k for k in objects]
    print(keys)
    records = []
    crs = None

    for key in tqdm(keys, total=len(keys), desc="Reading raster metadata", unit="raster"):
        print(key)
        s3_path = f"/vsis3/{bucket}/{key}"
        #s3_path = f"{key}"
        print("Trying to open S3 path:", s3_path)
        with rasterio.open(s3_path) as ds:
            print("s3_path",s3_path)
            if crs is None:
                crs = ds.crs

            left, bottom, right, top = ds.bounds
            records.append(
                {
                    "tile": key.split("/")[-1],
                    "geometry": box(left, bottom, right, top),
                }
            )

    return gpd.GeoDataFrame(records, crs=crs)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build raster footprints from raster outputs on S3."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )
    parser.add_argument(
        "--output",
        help="Local output GeoPackage path (default: tile_footprints.gpkg)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project = args.project.strip("/")
    print(project)

    footprints = build_tile_footprints(project)

    # Always write to a local temp file first
    with tempfile.TemporaryDirectory() as tmpdir:
        local_gpkg = os.path.join(tmpdir, "tile_footprints.gpkg")
        footprints.to_file(local_gpkg, driver="GPKG")

        s3_key = footprint_path(project)
        print("Uploading footprint to S3...")
        upload_file(
            local_path=local_gpkg,
            bucket=get_bucket(),
            s3_path=s3_key,
        )
        print(f"Footprint uploaded to: {s3_key}")



    
    # footprints.to_file(args.output, driver="GPKG")

    # s3_key = footprint_path(project)

    # print("Uploading footprint to S3...")
    # upload_file(
    #     local_path=args.output,
    #     bucket=get_bucket(),
    #     s3_path=s3_key,
    # )

    # print(f"Footprint uploaded to: {s3_key}")


if __name__ == "__main__":
    main()
