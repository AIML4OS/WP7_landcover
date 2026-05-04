from pathlib import Path
import tempfile

from landcover_pipeline.storage.s3 import (
    list_objects,
    download_file,
    upload_file,
    delete_object_prj,
    status_exists,
    write_status,
    remove_status,
)
from landcover_pipeline.storage.path import (
    raster_output_dir,
    vector_output_dir,
)
from landcover_pipeline.postprocessing.run_vector_engine import run_vector_engine


def run_vectorization(project_id: str, bucket: str, remove_raster: str = "N") -> None:
    print(f"▶ Starting vectorization for project {project_id}")

    raster_prefix = raster_output_dir(project_id)
    vector_prefix = vector_output_dir(project_id)

    raster_keys = list_objects(bucket=bucket, prefix=raster_prefix)

    total_tiles = 0
    skipped = 0
    completed = 0
    failed = 0

    for raster_key in raster_keys:

        if not raster_key.lower().endswith(".tif"):
            continue

        total_tiles += 1
        tile_id = Path(raster_key).stem
        vector_key = f"{vector_prefix}/{tile_id}.gpkg"

        # --- skip if already running ---
        if status_exists(project_id, tile_id, "vector", "running"):
            print(f"{tile_id} running → skipped")
            skipped += 1
            continue

        # --- skip if already done ---
        if status_exists(project_id, tile_id, "vector", "done"):
            print(f"{tile_id} done → skipped")
            skipped += 1
            continue

        write_status(project_id, tile_id, "vector", "running")

        try:
            with tempfile.TemporaryDirectory(prefix=f"vector_{tile_id}_") as workdir:
                workdir = Path(workdir)

                local_raster = workdir / f"{tile_id}.tif"
                local_vector = workdir / f"{tile_id}.gpkg"

                # 1. download raster
                download_file(bucket, raster_key, str(local_raster))

                # 2. run vectorization engine
                run_vector_engine(
                    input_raster=local_raster,
                    output_vector=local_vector,
                )

                # 3. upload vector
                upload_file(
                    local_path=str(local_vector),
                    bucket=bucket,
                    s3_path=vector_key,
                )

                print("uploaded into S3:", vector_key)

                # 4. cleanup raster (optional)
                if remove_raster == "Y":
                    delete_object_prj(bucket, raster_key)
                    remove_status(project_id, tile_id, "inference", "running")
                    remove_status(project_id, tile_id, "inference", "done")

            remove_status(project_id, tile_id, "vector", "running")
            write_status(project_id, tile_id, "vector", "done")
            completed += 1

        except Exception as e:
            print(f"✖ Vectorization failed for {tile_id}: {e}")
            remove_status(project_id, tile_id, "vector", "running")
            write_status(project_id, tile_id, "vector", "failed")
            failed += 1

    to_process = total_tiles - skipped - completed - failed

    # --- FINAL REPORT ---
    print("\n📊 Vectorization summary")
    print(f"  Total tiles:   {total_tiles}")
    print(f"  Completed:     {completed}")
    print(f"  Skipped:       {skipped}")
    print(f"  Failed:        {failed}")
    print(f"  To process:    {to_process}")
