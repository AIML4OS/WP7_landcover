# landcover_pipeline/cli/compute_stats.py

import argparse
import tempfile
from pathlib import Path
import os

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

from landcover_pipeline.storage.s3 import (
    get_bucket,
    upload_file,
    download_file,
)

from landcover_pipeline.storage.path import (
    landcover_stats_path,
    footprint_path,
    landcover_overlap_aoi_path,
    landcover_overlap_path
)

from landcover_pipeline.stats.compute import (
    build_overlap_cells,
    mask_overlap_cells_with_aoi,
    compute_weighted_counts2,
)
from landcover_pipeline.stats.compute2 import compute_weighted_counts_low_memory
from landcover_pipeline.cli.common import add_run_argument, resolve_project


# ============================================================
# CLI
# ============================================================

def parse_args():
    def parse_bool(value: str) -> bool:
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
        raise argparse.ArgumentTypeError("Use true or false")

    parser = argparse.ArgumentParser(
        description="Compute land cover statistics for a project"
    )

    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )

    parser.add_argument(
        "--aoi",
        required=True,
        help="AOI geopackage file (local path)",
    )

    parser.add_argument(
        "--resolution",
        type=float,
        required=True,
        help="Pixel resolution in meters",
    )
    parser.add_argument(
        "--low-memory",
        type=parse_bool,
        default=False,
        help="Use low-memory counting path from compute2.py (true/false, default: false).",
    )

    add_run_argument(parser)

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()
    project = resolve_project(args.project, args.run)
    resolution = args.resolution

    # classes = [
    #     "building","greenhouse","swimming_pool","impervious surface",
    #     "pervious surface","bare soil","water","snow",
    #     "herbaceous vegetation","agricultural land","plowed land",
    #     "vineyard","deciduous","coniferous","brushwood"
    # ]



    dict_classes = {0: 'building',
                    1: 'greenhouse',
                    2: 'swimming_pool',
                    3: 'impervious_surface',
                    4: 'pervious_surface',
                    5: "bare soil",
                    6: 'water',
                    7: 'snow',
                    8: "herbaceous vegetation",
                    9: "agricultural land",
                    10:"plowed land",
                    11: "vineyard",
                    12: "deciduous",
                    13: "coniferous",
                    14: "brushwood",
                    15: "clear cut",
                    16: "ligneous",
                    17: "mixed",
                    18: "undefined"} 
    


    print(f"▶ Computing statistics for project {project}")

    bucket = get_bucket()

    with tempfile.TemporaryDirectory(prefix="stats_") as tmpdir:

        tmpdir = Path(tmpdir)

        # --------------------------------------------------------
        # 1. Download footprint from S3
        # --------------------------------------------------------

        footprint_s3_key = footprint_path(project)
        local_footprint = tmpdir / "tile_footprints.gpkg"

        print("⬇ Downloading footprint from S3...",footprint_s3_key)
        download_file(
            bucket=bucket,
            s3_path=footprint_s3_key,
            local_path=str(local_footprint),
        )

        footprints = gpd.read_file(local_footprint)

        # --------------------------------------------------------
        # 2. Build overlap cells
        # --------------------------------------------------------

        overlap_path = tmpdir / "overlap_cells.gpkg"
        overlap_aoi_path = tmpdir / "overlap_cells_aoi.gpkg"

        cells = build_overlap_cells(footprints)
        cells.to_file(overlap_path, driver="GPKG")

        mask_overlap_cells_with_aoi(
            overlap_gpkg=str(overlap_path),
            aoi_gpkg=args.aoi,
            output_gpkg=str(overlap_aoi_path),
        )

        # --------------------------------------------------------
        # 3. Pixel counting
        # --------------------------------------------------------

        if args.low_memory:
            counts = compute_weighted_counts_low_memory(
                project,
                str(overlap_aoi_path),
            )
        else:
            counts = compute_weighted_counts2(
                project,
                str(overlap_aoi_path),
            )

        # --------------------------------------------------------
        # 4. Build output table
        # --------------------------------------------------------

        out_table = []
        for k in tqdm(sorted(counts), desc="Formatting results"):
            out_table.append((k, counts[k]))

        tableLC = pd.DataFrame(out_table, columns=["class", "pixel"])
        tableLC["LC%"] = tableLC.pixel / tableLC.pixel.sum()
        tableLC["Area LC"] = tableLC.pixel * resolution**2
        #tableLC.index = classes
        tableLC.index = map(dict_classes.get, tableLC["class"])
 

        local_csv = tmpdir / "landcover_stats.csv"
        tableLC.to_csv(local_csv, sep=";")

        # --------------------------------------------------------
        # 5. Upload to S3
        # --------------------------------------------------------
        basename_aoi = os.path.basename(args.aoi)
        #aio_name="".join(args.aoi.split(".gpkg")[:-1])
        aio_name="".join(basename_aoi.split(".gpkg")[:-1])
       
        
        s3_key = landcover_stats_path(project,aio_name=aio_name)
        print("⬆ Uploading land cover statistics to S3...")
        upload_file(
            local_path=str(local_csv),
            bucket=bucket,
            s3_path=s3_key,
        )
        print(f"✔ Statistics uploaded to: {s3_key}")

        s3_key = landcover_overlap_path(project,aio_name=aio_name)
        print("⬆ Uploading overlapping tiles gpkg to S3...")
        upload_file(
            local_path=str(overlap_path),
            bucket=bucket,
            s3_path=s3_key,
        )
        print(f"✔ overlapping tiles gpkg uploaded to: {s3_key}")

        s3_key = landcover_overlap_aoi_path(project,aio_name=aio_name)
        print("⬆ Uploading overlapping tiles in aoi gpkg to S3...")
        upload_file(
            local_path=str(overlap_aoi_path),
            bucket=bucket,
            s3_path=s3_key,
        )
        print(f"✔ overlapping tiles in aoi uploaded to: {s3_key}")


if __name__ == "__main__":
    main()
