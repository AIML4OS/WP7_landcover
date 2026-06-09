"""
S3 access layer for the Land Cover Pipeline.

This module provides a thin wrapper around boto3 for interacting with
S3-compatible object storage. It contains no pipeline logic and no
hardcoded paths.

Credentials must be provided via environment variables.
"""

import os

import boto3
from botocore.exceptions import ClientError
import tempfile
from pathlib import Path

from landcover_pipeline.storage.path import (
    imagery_dir,status_dir
)

def get_bucket():
    bucket=None
    bucket = bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("S3_BUCKET environment variable not set")
    return bucket


# ----------------------------
# Client helpers
# ----------------------------
def clear_status(project_id: str, tile_id: str,stage: str, bucket: str):
    client = get_s3_client()

    prefixes = [
        f"{status_dir(project_id, stage)}/{tile_id}.running",
        f"{status_dir(project_id, stage)}/{tile_id}.done",
        f"{status_dir(project_id, stage)}/{tile_id}.failed",
    ]

    for key in prefixes:
        try:
            client.delete_object(Bucket=bucket, Key=key)
            print(f"key deleted: {key}")
        except Exception as e:
            print(f"skip delete {key}: {e}")


def get_s3_client():
    """
    Returns a boto3 S3 client using environment-based credentials.
    """
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION"),
        endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),  # optional (CloudFerro / CDSE)
    )


def check_s3_credentials() -> None:
    """
    Verifies that required S3 credentials are available.
    """
    required = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing = [k for k in required if not os.getenv(k)]

    if missing:
        raise EnvironmentError(
            f"Missing required S3 environment variables: {', '.join(missing)}"
        )


# ----------------------------
# Basic operations
# ----------------------------

def upload_file(
    local_path: str,
    bucket: str,
    s3_path: str,
) -> None:
    """
    Uploads a local file to S3.

    Parameters
    ----------
    local_path : str
        Path to local file.
    bucket : str
        S3 bucket name.
    s3_path : str
        Full S3 key (relative to bucket).
    """
    client = get_s3_client()   
    client.upload_file(local_path, bucket, s3_path)


def skip_file_img(project_id,bucket,filePath):
    print("**",filePath.name)
    s3_imagery_prefix = imagery_dir(project_id)
    s3_key = f"{s3_imagery_prefix}{filePath.name}"
    print((bucket, s3_key))
    # --- skip if already present ---
    if object_exists(bucket, s3_key):
        print(f"⏭ Skipping upload (already exists): {s3_key}")
        return True
    else:
        return False

def clear_running(project_id: str, bucket: str,stage:str) -> None:
    prefix = status_dir(project_id,stage)
    keys = list_objects(bucket, prefix)

    for key in keys:
        if key.endswith(".running"):
            delete_object_prj(bucket, key)
            print(f"🧹 removed {key}")

def download_file(
    bucket: str,
    s3_path: str,
    local_path: str,
) -> None:
    """
    Downloads a file from S3 to local filesystem.
    """
    client = get_s3_client()
    print(bucket)
    client.download_file(bucket, s3_path, local_path)


def object_exists(bucket: str, s3_path: str) -> bool:
    """
    Checks whether an object exists on S3.
    """
    client = get_s3_client()
    try:
        client.head_object(Bucket=bucket, Key=s3_path)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


#def list_objects(bucket: str, prefix: str) -> list:

def list_objects(bucket, prefix, substring=None):
    # """
    # Lists all object keys under a given prefix.
    # """
    # client = get_s3_client()
    # paginator = client.get_paginator("list_objects_v2")

    # keys = []
    # for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
    #     for obj in page.get("Contents", []):
    #         keys.append(obj["Key"])

    # return keys

    """
    Check if an S3 object exists.
    s3_uri: str, e.g. 's3://bucket/key'
    Returns True if exists, False otherwise.
    """
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        print(page)
        for obj in page.get("Contents", []):
            key = obj["Key"]
            #if key.lower().endswith(".tif") and (substring is None or substring in key):
            #    yield f"s3://{bucket}/{key}"
            if substring is None or substring in key:
                yield key       


def delete_object_prj(bucket: str, key: str) -> None:
    """
    Deletes a single object from S3.
    """
    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=key)

def remove_status(project_id: str, tile_id: str,stage: str, status: str) -> None:
    bucket = get_bucket()       
    key = f"{status_dir(project_id, stage)}/{tile_id}.{status}"
    #key = f"{project_id}/status/{tile_id}.{status}"
    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=key)

def status_exists(project_id: str, tile_id: str,stage: str, status: str, bucket: str = None) -> bool:
    """
    Check whether a given status file exists for a tile using prefix listing.
    Compatible with restricted S3 permissions.
    """
    client = get_s3_client()

    bucket=get_bucket()

    #prefix = f"{project_id}/status/{tile_id}.{status}"
    prefix =  f"{status_dir(project_id, stage)}/{tile_id}.{status}"
    #print("* project_id",project_id)
    #print("* stage",stage)
    #print("status_dir(project_id, stage)",status_dir(project_id, stage))
    #print("* bucket",bucket)
    #print("* prefix",prefix)
    
    resp = client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix,
        MaxKeys=1,
    )
    
    return "Contents" in resp



def write_status(project_id: str, tile_id: str, stage:str, status: str, bucket: str = None) -> None:
    """
    Write a status marker file to S3.
    """
    client = get_s3_client()
    bucket=get_bucket()

    key = f"{status_dir(project_id, stage)}/{tile_id}.{status}"
    #key = f"{project_id}/status/{tile_id}.{status}"

    # Write empty object
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=b"",
        ContentType="text/plain",
    )
