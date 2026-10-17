import argparse
import os
import sys
from pathlib import Path

from landcover_pipeline.download.core import download_outputs
from landcover_pipeline.storage.path import raster_output_dir
from landcover_pipeline.cli.common import add_run_argument, resolve_project


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download raster outputs from land cover pipeline"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Local output directory",
    )

    add_run_argument(parser)

    args = parser.parse_args()

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("❌ Missing S3_BUCKET environment variable")
        sys.exit(1)

    download_outputs(
        bucket=bucket,
        s3_prefix=raster_output_dir(resolve_project(args.project, args.run)),
        local_dir=Path(args.output),
        extension=".tif",
    )


if __name__ == "__main__":
    main()
