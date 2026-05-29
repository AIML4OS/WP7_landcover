"""
CLI entry point for local preprocessing and upload.

Command:
    preprocess_landcover --config master.yml --input /data/orthophotos/
"""
import os
import argparse
import tempfile
from pathlib import Path

from landcover_pipeline.config.master import (  
    load_master_config,
    validate_master_config,
    build_project_id,
)

from landcover_pipeline.storage.path import  imagery_name

from landcover_pipeline.preprocessing.prepare_inputs import prepare_single_input

from landcover_pipeline.preprocessing.scan import scan_input_directory


#from landcover_pipeline.preprocessing.anifest import  append_to_anifest,init_anifest

from landcover_pipeline.preprocessing.upload import (
    upload_imagery
)

from landcover_pipeline.storage.s3 import check_s3_credentials,skip_file_img



def parse_args():
    parser = argparse.ArgumentParser(
        description="Local preprocessing for the Land Cover Pipeline"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to master YAML configuration file",
    )

    parser.add_argument(
        "--rgb",
        required=True,
        help="Directory containing RGB orthophotos",
    )

    parser.add_argument(
        "--infrared",
        required=False,
        help="Directory containing infrared orthophotos (optional)",
    )

    return parser.parse_args()

def main(): 
    args = parse_args()

    print("▶ Loading master configuration")
    cfg = load_master_config(args.config)
    validate_master_config(cfg)

    project_id = build_project_id(cfg)
    
    bucket=None
    bucket = bucket or os.environ.get("S3_BUCKET")
    if not bucket:
        raise EnvironmentError("S3_BUCKET environment variable not set")

    #bucket = cfg["output"]["bucket"]
    model_variant = cfg["model"]["variant"]

    print(f"▶ Project ID: {project_id}")
    print(f"▶ Model variant: {model_variant}")
    print(f"▶ Target bucket: {bucket}")

    print("▶ Checking S3 credentials")
    check_s3_credentials()

    print("▶ Scanning RGB inputs")
    rgb_files = scan_input_directory(args.rgb)
    ir_files = None
    if args.infrared:
        print("▶ Scanning infrared inputs")
        ir_files = scan_input_directory(args.infrared)

    print("▶ Starting streaming preprocessing")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        processed_count = 0



        #anifest_path = tmpdir / "anifest.ndjson"

        ## Header del anifest (una sola volta)
        #init_anifest(
        #    anifest_path,
        #    header={
        #        "project_id": project_id,
        #    },
        #)


        # Upload iniziale del anifest (opzionale ma consigliato)
        #upload_anifest(anifest_path, project_id, bucket)


        for idx, rgb in enumerate(rgb_files):

            ir = ir_files[idx] if ir_files else None

            print(f"▶ Processing file {idx + 1}/{len(rgb_files)}: {rgb.name}")
                                
            prepared_img= tmpdir / Path(imagery_name(project_id,rgb,model_variant) )
            skip=skip_file_img(project_id,bucket,prepared_img)

            if skip:
                continue

            
            prepare_single_input(
                rgb=rgb,
                ir=ir,
                model_variant=model_variant,
                out_path=prepared_img,
            )

            upload_imagery(prepared_img, project_id, bucket)


            ## Append al anifest
            #append_to_anifest(
            #    anifest_path,
            #    entry={
            #        "img_filename": prepared.name,
            #        "s3_key": s3_key,
            #        "model_variant": model_variant,
            #    },
            #)

            ## Overwrite del anifest in S3 (robusto, resume-friendly)
            #upload_anifest(anifest_path, project_id, bucket)
            #with open(anifest_path,"r") as ff:
            #    for row in ff:
            #        print(row)

            processed_count += 1

        print(f"✔ Processed and uploaded {processed_count} files")


if __name__ == "__main__":
    main()
