# landcover_pipeline/cli/vectorize.py

import argparse
import os
import sys

from landcover_pipeline.postprocessing.vector import run_vectorization
from landcover_pipeline.storage.s3 import get_bucket,clear_running


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vectorize land cover raster outputs"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )
    parser.add_argument(
        "--remove_raster",
        required=False,
        help="Remove raster in S3 after conversion Y/N",
    )


    args = parser.parse_args()

    bucket = get_bucket()

    clear_running(args.project,bucket,"vector")

    run_vectorization(
        project_id=args.project.strip("/"),
        bucket=bucket,
        remove_raster=args.remove_raster
    )


if __name__ == "__main__":
    main()
