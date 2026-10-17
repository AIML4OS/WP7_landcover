import argparse

from landcover_pipeline.quality.probabilities import run_quality_probabilities
from landcover_pipeline.cli.common import add_run_argument, resolve_project
from landcover_pipeline.inference.bands import validate_run
from landcover_pipeline.storage.path import run_name


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run FLAIR probabilities on crop rasters stored in S3."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )
    parser.add_argument(
        "--crop-size",
        type=int,
        default=600,
        help="Crop size in pixels used in the S3 namespace tile_crops/<crop_size>.",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["small", "large", "flairhub"],
        help="FLAIR model size (default: small).",
    )
    parser.add_argument(
        "--nsample",
        type=int,
        default=None,
        help="If set, process a random sample of N missing crop tiles.",
    )
    add_run_argument(parser)
    args = parser.parse_args()
    try:
        validate_run(args.model, run_name(resolve_project(args.project, args.run)))
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main():
    args = parse_args()
    summary = run_quality_probabilities(
        project_id=resolve_project(args.project, args.run),
        crop_size=args.crop_size,
        model=args.model,
        nsample=args.nsample,
    )

    print("Quality probabilities summary")
    print(f"  Project:               {summary['project']}")
    print(f"  S3 crops dir:          {summary['s3_crop_dir']}")
    print(f"  S3 probabilities dir:  {summary['s3_prob_dir']}")
    print(f"  Crop size:             {summary['crop_size']}")
    print(f"  Model:                 {summary['model']}")
    print(f"  Total crops found:     {summary['total_crops']}")
    print(f"  Skipped (already done):{summary['skipped']}")
    print(f"  Missing total:         {summary['missing']}")
    print(f"  Selected to process:   {summary['selected_to_process']}")
    print(f"  Processed:             {summary['processed']}")
    if summary["failed"]:
        print(f"  Failed:                {len(summary['failed'])}")
        for key in summary["failed"][:10]:
            print(f"    - {key}")


if __name__ == "__main__":
    main()
