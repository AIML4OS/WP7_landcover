# inference/runner.py
from pathlib import Path
from typing import Optional

from landcover_pipeline.storage.s3 import (
    list_objects,
    status_exists,
    write_status,
    remove_status,
)
from landcover_pipeline.storage.path import (
    imagery_dir,
    run_name,
)
from landcover_pipeline.inference.flair import run_flair_single
from landcover_pipeline.inference.bands import skip_reason


def run_inference(
    project_id: str,
    bucket: str,
    model: str,
    use_gpu: Optional[bool] = None,
    batch_size: Optional[int] = None,
    num_worker: Optional[int] = None,
) -> None:
    print(f"▶ Starting inference for project {project_id}")

    imagery_prefix = imagery_dir(project_id)

    input_keys = list_objects(
        bucket=bucket,
        prefix=imagery_prefix,
    )
    
    total = 0
    skipped = 0
    incompatible = 0
    completed = 0
    failed = 0

    for input_key in input_keys:
        if not input_key.lower().endswith(".tif"):
            continue

        total += 1

        tile_id = Path(input_key).stem

        # --- tile that cannot be read by this run (e.g. no IR band for run irg) ---
        if run_name(project_id) is not None:
            reason = skip_reason(project_id, tile_id)
            if reason:
                print(f"⏭ Skipping {tile_id}: {reason}")
                incompatible += 1
                continue

        # --- SKIP logic ---
        if status_exists(project_id, tile_id,"inference", "done"):
            skipped += 1
            continue

        if status_exists(project_id, tile_id,"inference", "running"):
            skipped += 1
            continue

        print(f"▶ Processing {tile_id}")
        write_status(project_id, tile_id,"inference", "running")


        #try:
        if True:
            run_flair_single(
                project_id=project_id,
                input_key=input_key,
                tile_id=tile_id,
                model=model,
                use_gpu=use_gpu,
                batch_size=batch_size,
                num_worker=num_worker,
            )
            remove_status(project_id, tile_id,"inference", "running")
            write_status(project_id, tile_id,"inference", "done")
            completed += 1

        #except Exception as e:
        #    print(f"✖ Failed {tile_id}: {e}")
        #    remove_status(project_id, tile_id, "running")
        #    write_status(project_id, tile_id, "failed")
        #    failed += 1

    print("✔ Inference finished")
    print(f"  Total input files: {total}")
    print(f"  Skipped:           {skipped}")
    print(f"  Not readable by run: {incompatible}")
    print(f"  Completed:         {completed}")
    print(f"  Failed:            {failed}")
