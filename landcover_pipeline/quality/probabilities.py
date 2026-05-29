from pathlib import Path
import random
from typing import Optional

from landcover_pipeline.inference.flair import run_flair_single
from landcover_pipeline.storage.path import (
    quality_probability_dir,
    quality_probability_path,
    quality_work_dir,
)
from landcover_pipeline.storage.s3 import get_bucket, list_objects


def run_quality_probabilities(
    project_id: str,
    crop_size: int = 600,
    model: str = "small",
    print_initial_report: bool = True,
    nsample: Optional[int] = None,
) -> dict:
    project = project_id.strip("/")
    bucket = get_bucket()

    s3_crop_dir = f"{quality_work_dir(project)}/tile_crops/{crop_size}"
    s3_prob_dir = quality_probability_dir(project, crop_size, model=model)
    crop_keys = sorted(
        key for key in list_objects(bucket=bucket, prefix=s3_crop_dir)
        if key.lower().endswith(".tif")
    )
    existing_prob_keys = set(
        key for key in list_objects(bucket=bucket, prefix=s3_prob_dir)
        if key.lower().endswith(".tif")
    )
    already_done_prob_keys: list[str] = []
    missing_crop_keys: list[str] = []

    for input_key in crop_keys:
        tile_id = Path(input_key).stem
        output_key = quality_probability_path(project, crop_size, tile_id, model=model)
        if output_key in existing_prob_keys:
            already_done_prob_keys.append(output_key)
        else:
            missing_crop_keys.append(input_key)

    missing_total = len(missing_crop_keys)
    if nsample is not None:
        if nsample <= 0:
            raise ValueError("nsample must be > 0 when provided")
        to_process_keys = random.sample(
            missing_crop_keys, min(nsample, missing_total)
        )
    else:
        to_process_keys = missing_crop_keys

    processed = 0
    skipped = len(already_done_prob_keys)
    failed: list[str] = []

    if print_initial_report:
        print("Initial idempotency check")
        print(f"  Already computed:      {len(already_done_prob_keys)}")
        for key in already_done_prob_keys:
            print(f"    - {key}")
        print(f"  Total crop tiles:      {len(crop_keys)}")
        print(f"  Missing to compute:    {missing_total}")
        print(f"  Selected to process:   {len(to_process_keys)}")
        for key in to_process_keys:
            print(f"    - {key}")

    for input_key in to_process_keys:
        tile_id = Path(input_key).stem
        output_key = quality_probability_path(project, crop_size, tile_id, model=model)
        try:
            run_flair_single(
                project,
                input_key,
                tile_id,
                model,
                output_class="prob",
                output_s3_key=output_key,
            )
            existing_prob_keys.add(output_key)
            processed += 1
        except Exception as e:
            print(e)
            failed.append(input_key)

    return {
        "project": project,
        "s3_crop_dir": s3_crop_dir,
        "s3_prob_dir": s3_prob_dir,
        "model": model,
        "crop_size": crop_size,
        "total_crops": len(crop_keys),
        "already_done": already_done_prob_keys,
        "to_process": to_process_keys,
        "missing": missing_total,
        "selected_to_process": len(to_process_keys),
        "skipped": skipped,
        "processed": processed,
        "failed": failed,
    }
