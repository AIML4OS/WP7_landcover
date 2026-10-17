# landcover_pipeline/cli/monitor.py

import argparse
import os
import sys

from landcover_pipeline.monitor.monitor import monitor_landcover
from landcover_pipeline.cli.common import add_run_argument, resolve_project


def main() -> None:
    stage="inference"
    parser = argparse.ArgumentParser(
        description="Monitor land cover inference execution status"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )

    add_run_argument(parser)

    args = parser.parse_args()

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("❌ Missing S3_BUCKET environment variable")
        sys.exit(1)

    monitor_landcover(
        project_id=resolve_project(args.project, args.run),
        bucket=bucket,
        stage=stage
    )


if __name__ == "__main__":
    main()
