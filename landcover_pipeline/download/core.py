from pathlib import Path
from landcover_pipeline.storage.s3 import list_objects, download_file


def download_outputs(
    bucket: str,
    s3_prefix: str,
    local_dir: Path,
    extension: str,
) -> None:
    """
    Download files from S3 prefix into local directory with idempotent behavior.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    keys = list_objects(bucket=bucket, prefix=s3_prefix)

    total = 0
    skipped = 0
    downloaded = 0

    for key in keys:
        if not key.lower().endswith(extension):
            continue

        total += 1
        filename = Path(key).name
        local_path = local_dir / filename

        if local_path.exists():
            skipped += 1
            continue

        download_file(
            bucket=bucket,
            s3_path=key,
            local_path=str(local_path),
        )
        downloaded += 1

    print("\n📥 Download summary")
    print(f"  Total files:   {total}")
    print(f"  Downloaded:    {downloaded}")
    print(f"  Skipped:       {skipped}")
