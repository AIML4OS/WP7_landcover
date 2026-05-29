"""
Upload utilities for the Land Cover Pipeline.

This module uploads locally prepared inputs to S3 according to the
canonical storage layout defined in storage.path.
"""

from pathlib import Path
from typing import List

from landcover_pipeline.storage.s3 import upload_file,    object_exists
from landcover_pipeline.storage.path import (
    imagery_dir,
    master_config_path,
    #anifest_path,
)





'''
def upload_imagery(
    filePath: Path,
    project_id: str,
    bucket: str,
) -> str:
    """
    Upload imagery files to S3.

    Parameters
    ----------
    files : Path
        Local raster file.
    project_id : str
        <COUNTRY>/<REGION>/<DATE>
    bucket : str
        S3 bucket name.
    """
    s3_imagery_prefix = imagery_dir(project_id)

    
    s3_key = f"{s3_imagery_prefix}{filePath.name}"
    upload_file(
        local_path=str(filePath),
        bucket=bucket,
        s3_path=s3_key,
    )
    return s3_key
'''


def upload_imagery(
    filePath: Path,
    project_id: str,
    bucket: str,
) -> str:
    """
    Upload a single imagery file to S3, skipping upload if the file
    already exists.

    Parameters
    ----------
    filePath : Path
        Local raster file.
    project_id : str
        <COUNTRY>/<REGION>/<DATE>
    bucket : str
        S3 bucket name.

    Returns
    -------
    str
        S3 key of the imagery file.
    """
    s3_imagery_prefix = imagery_dir(project_id)
    s3_key = f"{s3_imagery_prefix}{filePath.name}"
    print("s3_key",s3_key)

    # --- skip if already present ---
    #if object_exists(bucket, s3_key):
    #    print(f"⏭ Skipping upload (already exists): {s3_key}")
    #    return s3_key

    # --- upload ---
    print(f"⬆ Uploading {filePath.name} to {s3_key}")
    upload_file(
        local_path=str(filePath),
        bucket=bucket,
        s3_path=s3_key,
    )

    return s3_key





def upload_master_config(
    master_config_path_local: str,
    project_id: str,
    bucket: str,
) -> None:
    """
    Upload master YAML configuration to S3.
    """
    upload_file(
        local_path=master_config_path_local,
        bucket=bucket,
        s3_path=master_config_path(project_id),
    )


#def upload_anifest(
#    anifest_path_local: str,
#    project_id: str,
#    bucket: str,
#) -> None:
#    """
#    Upload anifest.json to S3.
#    """
#    upload_file(
#        local_path=anifest_path_local,
#        bucket=bucket,
#        s3_path=anifest_path(project_id),
#    )
