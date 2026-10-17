import argparse
import importlib.util
from pathlib import Path

from landcover_pipeline.storage.path import quality_probability_dir
from landcover_pipeline.storage.s3 import get_bucket
from landcover_pipeline.cli.common import add_run_argument, resolve_project


def _load_extract_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Pipeline code for accuracy assessment"
        / "extract_predictions.py"
    )
    spec = importlib.util.spec_from_file_location("quality_extract_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract prediction bands at coordinates from quality probability rasters on S3."
    )
    parser.add_argument("--project", required=True, help="Project identifier <COUNTRY>/<REGION>/<DATE>.")
    parser.add_argument("--crop-size", required=True, type=int, help="Crop-size namespace in quality/probability.")
    parser.add_argument(
        "--model",
        default="small",
        choices=["small", "large", "flairhub"],
        help="Model namespace suffix used in quality/probability/<crop-size>_<model>.",
    )
    parser.add_argument("--coord-file", required=True, help="Tab-separated coordinates file.")
    parser.add_argument(
        "--output-folder",
        default="landcover_pipeline/Pipeline code for accuracy assessment",
        help="Local output folder (default: legacy assessment folder).",
    )
    parser.add_argument("--additional-cols", default="SURVEY_LC1,SURVEY_LC2")
    parser.add_argument("--easting-col", default="EASTING_ETRS89")
    parser.add_argument("--northing-col", default="NORTHING_ETRS89")
    parser.add_argument("--point-id-col", default="POINT_ID")
    add_run_argument(parser)
    return parser.parse_args()


def main():
    args = parse_args()
    module = _load_extract_module()

    project = resolve_project(args.project, args.run)
    bucket = get_bucket()
    s3_prefix = quality_probability_dir(project, args.crop_size, model=args.model)
    tif_folder = f"s3://{bucket}/{s3_prefix}"

    out_dir = Path(args.output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"predictions_{project.replace('/', '_')}_crop{args.crop_size}.txt"

    summary = module.extract_predictions_from_s3(
        coord_file=args.coord_file,
        tif_folder=tif_folder,
        output_file=str(output_file),
        additional_cols=[c.strip() for c in args.additional_cols.split(",") if c.strip()],
        easting_col=args.easting_col,
        northing_col=args.northing_col,
        point_id_col=args.point_id_col,
    )
    print("Extract summary")
    print(f"  s3 tif folder: {summary['tif_folder']}")
    print(f"  tif count:   {summary['tif_count']}")
    print(f"  output file: {summary['output_file']}")
    print(f"  log file:    {summary['log_path']}")


if __name__ == "__main__":
    main()

