import argparse
import os
import sys

from landcover_pipeline.storage.s3 import list_objects, delete_object_prj,get_bucket
from landcover_pipeline.storage.path import status_dir,raster_output_dir,vector_output_dir


def clear_stage(stage: str,project_id : str) -> None:


    bucket = get_bucket()

    prefix_stat = status_dir(project_id,stage)
    keys_stat = list_objects(bucket=bucket, prefix=prefix_stat)

    if stage=="inference":
        prefix_out = raster_output_dir(project_id)
    if stage=="vector":
        prefix_out = vector_output_dir(project_id)

    keys_output_out = list_objects(bucket=bucket, prefix=prefix_out)
    
    if not keys_stat:
        print("ℹ No status files found")
    if not keys_output_out:
        if stage=="inference":
            print("ℹ No raster inference output files found")
        if stage=="vector":
            print("ℹ No vector files found")

    if (len(keys_stat)>0):
        print(f"⚠ You are about to delete {len(keys_stat)} status files:")
        print(f"  S3 prefix: {prefix_stat}")
        print("  This operation cannot be undone.")

    if (len(keys_output_out)>0):
        if stage=="inference":
            print(f"⚠ You are about to delete {len(keys_output_out)} raster inference files:")
        if stage=="vector":
            print(f"⚠ You are about to delete {len(keys_output_out)} vector files:")
                        
        print(f"  S3 prefix: {prefix_out}")
        print("  This operation cannot be undone.")

    if (len(keys_stat)>0)|(len(keys_output_out)>0):
        confirm = input("Type 'YES' to confirm: ")

        if confirm != "YES":
            print("❌ Aborted")
            return

        for key in keys_stat:
            delete_object_prj(bucket=bucket, key=key)
            print(f"🧹 deleted {key}")

        print("✔ Status directory cleared successfully")


        for key in keys_output_out:
            delete_object_prj(bucket=bucket, key=key)
            print(f"🧹 deleted {key}")

        print("✔ directory cleared successfully")    


