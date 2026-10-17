"""
CLI entry point for local preprocessing and upload.

Imagery is stored by content, not by model:
    <tile>_RGB.tif    3 bands  R,G,B
    <tile>_RGBI.tif   4 bands  R,G,B,IR
The choice between RGB and IRG reading is made at inference time.

Commands:
    preprocess --project IT/veneto/2021 --rgb /data/rgb
    preprocess --project IT/veneto/2021 --rgb /data/rgb --infrared /data/ir
    preprocess --project IT/veneto/2021 --rgbi /data/rgbi
    preprocess --project IT/veneto/2021 --irgb /data/irgb
"""
import os
import argparse
import tempfile
from pathlib import Path

from landcover_pipeline.preprocessing.prepare_inputs import (
    plan_jobs,
    check_job,
    prepare_job,
)

from landcover_pipeline.preprocessing.scan import scan_input_directory

from landcover_pipeline.preprocessing.upload import (
    upload_imagery
)

from landcover_pipeline.storage.s3 import check_s3_credentials, skip_file_img


def parse_args():
    parser = argparse.ArgumentParser(
        description="Local preprocessing for the Land Cover Pipeline"
    )

    parser.add_argument(
        "--project",
        required=True,
        help="Project id <country>/<region>/<year>, e.g. IT/veneto/2021",
    )

    parser.add_argument(
        "--rgb",
        help="Directory with 3-band R,G,B orthophotos "
             "(stored as *_RGB.tif, or *_RGBI.tif when --infrared is given)",
    )

    parser.add_argument(
        "--rgbi",
        help="Directory with 4-band R,G,B,IR orthophotos (stored as *_RGBI.tif)",
    )

    parser.add_argument(
        "--irgb",
        help="Directory with 4-band IR,R,G,B orthophotos "
             "(reordered to R,G,B,IR, stored as *_RGBI.tif)",
    )

    parser.add_argument(
        "--infrared",
        help="Directory with 1-band infrared orthophotos, paired by file name "
             "with the files in --rgb",
    )

    args = parser.parse_args()

    args.project = args.project.strip("/")
    if not args.project:
        parser.error("--project must not be empty")
    if not (args.rgb or args.rgbi or args.irgb):
        parser.error("give at least one of --rgb, --rgbi, --irgb")
    if args.infrared and not args.rgb:
        parser.error("--infrared can only be used together with --rgb")

    return args


def main():
    args = parse_args()

    project_id = args.project

    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("S3_BUCKET environment variable not set")

    print(f"▶ Project ID: {project_id}")
    print(f"▶ Target bucket: {bucket}")

    print("▶ Checking S3 credentials")
    check_s3_credentials()

    print("▶ Scanning inputs")
    jobs = plan_jobs(
        rgb_files=scan_input_directory(args.rgb) if args.rgb else [],
        rgbi_files=scan_input_directory(args.rgbi) if args.rgbi else [],
        irgb_files=scan_input_directory(args.irgb) if args.irgb else [],
        ir_files=scan_input_directory(args.infrared) if args.infrared else None,
    )

    # Validate every file before processing anything
    print(f"▶ Checking {len(jobs)} input file(s)")
    problems = []
    for job in jobs:
        try:
            check_job(job)
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        raise SystemExit(
            "Input check failed, nothing uploaded:\n  " + "\n  ".join(problems)
        )

    print("▶ Starting streaming preprocessing")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        processed_count = 0

        for idx, job in enumerate(jobs):

            print(f"▶ Processing file {idx + 1}/{len(jobs)}: {job.src.name} -> {job.out_name}")

            prepared_img = tmpdir / job.out_name
            if skip_file_img(project_id, bucket, prepared_img):
                continue

            prepare_job(job, prepared_img)

            upload_imagery(prepared_img, project_id, bucket)
            prepared_img.unlink(missing_ok=True)   # free disk space

            processed_count += 1

        print(f"✔ Processed and uploaded {processed_count} files")


if __name__ == "__main__":
    main()
