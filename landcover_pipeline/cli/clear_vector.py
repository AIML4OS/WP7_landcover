import argparse


from landcover_pipeline.clear.clear import clear_stage
from landcover_pipeline.cli.common import add_run_argument, resolve_project


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

    add_run_argument(parser)

    args = parser.parse_args()
    project_id = resolve_project(args.project, args.run)

    clear_stage(stage,project_id) 


if __name__ == "__main__":
    main()
