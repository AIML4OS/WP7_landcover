import argparse


from landcover_pipeline.clear.clear import clear_stage


def main() -> None:
    stage="vector"
    parser = argparse.ArgumentParser(
        description="Clear all status files for a land cover project"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project identifier <COUNTRY>/<REGION>/<DATE>",
    )

    args = parser.parse_args()
    project_id =args.project

    clear_stage(stage,project_id) 


if __name__ == "__main__":
    main()
