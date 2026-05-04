from pathlib import Path

from landcover_pipeline.storage.s3 import list_objects
from landcover_pipeline.storage.path import imagery_dir, status_dir, raster_output_dir


def monitor_landcover(project_id: str, bucket: str,stage:str) -> None:
    print(f"📊 Monitoring project {project_id}\n")
    
    if stage=="inference":
        imagery_input_prefix = imagery_dir(project_id)
    if stage=="vector":
        imagery_input_prefix = raster_output_dir(project_id)

    status_prefix = status_dir(project_id,stage)+"/"

    # --- list inputs ---
    imagery_keys = list_objects(bucket=bucket, prefix=imagery_input_prefix)
    tile_ids = {
        Path(k).stem
        for k in imagery_keys
        if k.lower().endswith(".tif")
    }

    # --- list statuses ---
    status_keys = list_objects(bucket=bucket, prefix=status_prefix)
    
    done = set()
    running = set()
    failed = set()

    for key in status_keys:
        name = Path(key).name
        if name.endswith(".done"):
            done.add(name.replace(".done", ""))
        elif name.endswith(".running"):
            running.add(name.replace(".running", ""))
        elif name.endswith(".failed"):
            failed.add(name.replace(".failed", ""))

    pending = tile_ids - done - running - failed

    # --- report ---
    print()
    print("--- report ---")
    
    print()
    print(f"Total tiles: {len(tile_ids)}")
    print(f"To process:  {len(pending)}")
    print(f"Completed:   {len(done)}")
    print(f"Running:     {len(running)}")
    print(f"Failed:      {len(failed)}")
    

    if failed:
        print("\n⚠ Failed tiles:")
        for t in sorted(failed):
            print(f"  - {t}")

    if not pending and not running:
        print("\n✔ JOB COMPLETED")
    elif running:
        print("\n⏳ JOB IN PROGRESS")
    elif pending:
        print("\n SOME FILES TO PROCESS")
