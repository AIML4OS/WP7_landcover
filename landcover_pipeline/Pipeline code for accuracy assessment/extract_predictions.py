"""
Extract Flair class probabilities at user-provided coordinates.

Current implementation:
- reads tif rasters directly from S3 (tif_folder as s3://bucket/prefix)
- keeps metadata columns configurable to switch modality in future
"""

import os
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from landcover_pipeline.quality.utils import process_tif_file, read_coordinates
from landcover_pipeline.storage.s3 import get_bucket, get_s3_client

def _parse_s3_folder(tif_folder: str):
    folder = str(tif_folder).strip()
    if folder.startswith("s3://"):
        no_scheme = folder[len("s3://"):]
        bucket, _, prefix = no_scheme.partition("/")
        return bucket, prefix.strip("/")
    raise ValueError("tif_folder must be in format s3://<bucket>/<prefix>")


def extract_predictions_from_s3(
    coord_file: str,
    tif_folder: str,
    output_file: str,
    additional_cols=None,
    easting_col: str = "EASTING_ETRS89",
    northing_col: str = "NORTHING_ETRS89",
    point_id_col: str = "POINT_ID",
) -> dict:
    # Column presets you may switch to in future:
    # - LUCAS mode: additional_cols = ["SURVEY_LC1", "SURVEY_LC2"]
    # - STRATA mode: additional_cols = ["STRATUM_LUCAS", "STR18"]
    # - Custom mode: additional_cols = ["real"]
    if additional_cols is None:
        additional_cols = ["SURVEY_LC1", "SURVEY_LC2"]

    bucket, prefix = _parse_s3_folder(tif_folder)
    if not bucket:
        bucket = get_bucket()

    target_coords = read_coordinates(
        coord_file, easting_col, northing_col, point_id_col, additional_cols
    )
    print(f"Loaded {len(target_coords)} coordinates")

    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    tif_entries = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".tif"):
                tif_entries.append((key, int(obj.get("Size", 0))))

    if not tif_entries:
        raise ValueError(f"No tif found in s3://{bucket}/{prefix}")

    tif_root = f"/vsis3/{bucket}"
    log_path = output_file.replace(".txt", "_summary.log")

    with open(output_file, "w") as f_out:
        band_headers = "\t".join([f"band_{i}" for i in range(1, 20)])
        additional_headers = "\t".join(additional_cols) if additional_cols else ""
        additional_headers_str = f"\t{additional_headers}" if additional_headers else ""
        f_out.write(
            f"point_id\tpixel_row_index\tpixel_col_index\tinput_easting\tinput_northing\t"
            f"pixel_easting\tpixel_northing{additional_headers_str}\t{band_headers}\tsource_file\n"
        )

        skipped_coords = {}
        with ProcessPoolExecutor() as executor:
            futures = {
                executor.submit(process_tif_file, key, tif_root, target_coords, additional_cols): (key, size)
                for key, size in tif_entries
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing .tif files"):
                results, filename, skipped_count = future.result()
                _, size_bytes = futures[future]
                tqdm.write(f"file: {filename} | size: {size_bytes} bytes ({size_bytes / (1024*1024):.2f} MB)")
                if skipped_count > 0:
                    skipped_coords[filename] = skipped_count
                for result in results:
                    f_out.write(result)

    with open(log_path, "w") as log:
        log.write("Summary of skipped coordinates due to out-of-bounds:\n\n")
        total_skips = sum(skipped_coords.values())
        for fname, count in skipped_coords.items():
            log.write(f"{fname}: {count} coordinates skipped\n")
        log.write(f"\nTotal skipped: {total_skips} coordinates across {len(skipped_coords)} files.\n")

    return {
        "coord_file": coord_file,
        "tif_folder": tif_folder,
        "output_file": output_file,
        "log_path": log_path,
        "tif_count": len(tif_entries),
    }


if __name__ == "__main__":
    # Backward-compatible manual run defaults
    # coord_file examples:
    # - ".../DK_LUCAS_2022_DK01_EPSG25832.txt"
    # - ".../LUCAS-Master-Grid_DK01_EPSG25832.txt"
    #
    # tif_folder example:
    # - "s3://<bucket>/IT/veneto/2021/quality/probability/2176"
    #
    # output_file example:
    # - "small_irg_predictions_DK_LUCAS_2022_DK01_EPSG25832.txt"
    coord_file = "landcover_pipeline/Pipeline code for accuracy assessment/DK_LUCAS_2022_ DK01_EPSG25832.txt"
    tif_folder = "s3://my-bucket/path/to/probabilities"
    output_file = "predictions_output.txt"
    extract_predictions_from_s3(
        coord_file=coord_file,
        tif_folder=tif_folder,
        output_file=output_file,
        additional_cols=["SURVEY_LC1", "SURVEY_LC2"],
    )
