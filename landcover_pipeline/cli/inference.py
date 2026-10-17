# cli/run_inference.py

import argparse,os
from landcover_pipeline.inference.runner import run_inference

from landcover_pipeline.storage.s3 import clear_running
from landcover_pipeline.cli.common import add_run_argument, resolve_project
from landcover_pipeline.inference.bands import validate_run
from landcover_pipeline.storage.path import run_name

def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Use true or false")


def _int_min(minimum: int):
    def parse(value: str) -> int:
        number = int(value)
        if number < minimum:
            raise argparse.ArgumentTypeError(f"Must be >= {minimum}")
        return number
    return parse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    add_run_argument(parser)
    parser.add_argument("--model", required=True)
    parser.add_argument("--use-gpu", type=_parse_bool, default=None,
                        help="Override use_gpu from the template (true/false)")
    parser.add_argument("--batch-size", type=_int_min(1), default=None,
                        help="Override batch_size from the template")
    parser.add_argument("--num-worker", type=_int_min(0), default=None,
                        help="Override num_worker from the template")

    args = parser.parse_args()

    if args.model != "flairhub" and any(
        v is not None for v in (args.use_gpu, args.batch_size, args.num_worker)
    ):
        parser.error("--use-gpu, --batch-size and --num-worker require --model flairhub")

    try:
        project_id = resolve_project(args.project, args.run)
        validate_run(args.model, run_name(project_id))
    except ValueError as exc:
        parser.error(str(exc))

    bucket=None
    bucket = bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("S3_BUCKET environment variable not set")
    
    clear_running(project_id,bucket,"inference")
    run_inference(
        project_id,
        bucket,
        args.model,
        use_gpu=args.use_gpu,
        batch_size=args.batch_size,
        num_worker=args.num_worker,
    )

if __name__ == "__main__":
    main()

