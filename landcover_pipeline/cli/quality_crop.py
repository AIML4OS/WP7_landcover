import argparse

from landcover_pipeline.quality.tiles_crop import run_tiles_crop


def parse_args():
    parser = argparse.ArgumentParser(
        description="Crop input tiles around LUCAS points in AOI and upload results to S3."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )
    parser.add_argument(
        "--lucas-csv",
        required=True,
        help="Local path to LUCAS csv",
    )
    parser.add_argument(
        "--aoi",
        required=True,
        help="Local path to AOI geopackage",
    )
    parser.add_argument(
        "--crop-size",
        type=int,
        default=600,
        help="Crop size in pixels (default: 600)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    summary = run_tiles_crop(
        project_id=args.project,
        lucas_csv=args.lucas_csv,
        aoi_path=args.aoi,
        crop_size=args.crop_size,
    )

    print("Crop quality summary")
    print(f"  Project:               {summary['project']}")
    print(f"  S3 work dir:           {summary['s3_work_dir']}")
    print(f"  S3 crops dir:          {summary['s3_crop_dir']}")
    print(f"  Points in AOI:         {summary['points_total']}")
    print(f"  Point/tile pairs:      {summary['valid_point_tile_pairs']}")
    print(f"  Tiles processed:       {summary['tiles_processed']}")
    print(f"  Crops uploaded:        {summary['crops_uploaded']}")
    print(f"  Points table key:      {summary['s3_table_key']}")
    if summary["missing_tiles"]:
        print(f"  Missing tiles on S3:   {len(summary['missing_tiles'])}")
        for key in summary["missing_tiles"][:10]:
            print(f"    - {key}")


if __name__ == "__main__":
    main()
