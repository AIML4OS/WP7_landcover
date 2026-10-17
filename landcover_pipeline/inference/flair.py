# inference/flair.py
import time
from pathlib import Path
from typing import Optional
from landcover_pipeline.template.yml_config import update_yaml_config
from landcover_pipeline.storage.s3 import download_file,get_bucket, object_exists
from landcover_pipeline.storage.path import raster_output_fullname
from  landcover_pipeline.storage.s3 import upload_file
import tempfile
import subprocess
import os
from landcover_pipeline.inference.flairhub import run_flairhub_single
from landcover_pipeline.inference.bands import resolve_bands

FLAIRHUB_MODEL = "flairhub"

def run_flair1_single(
    project_id: str,
    input_key: str,
    tile_id: str,
    model: str,
    output_class: str="argmax",
    output_s3_key: Optional[str] = None,
) -> None:
    
    """
    Runs FLAIR on a single input raster.
    """

    with tempfile.TemporaryDirectory(prefix=f"flair_{tile_id}_") as work_dir:
        with tempfile.TemporaryDirectory(prefix=f"flair_out_") as local_outdir:
            work_dir=Path(work_dir)
            
            # --- create temp working dir ---
            local_input = str((work_dir / Path(tile_id+".tif")).absolute())
            local_outdir = str(Path(local_outdir).absolute())

            # --- create temp working dir ---
            #work_dir = Path(tempfile.mkdtemp(prefix=f"flair_{tile_id}_"))
            #local_input = str((work_dir / Path(tile_id+".tif")).absolute())
            #local_outdir = str(Path(tempfile.mkdtemp(prefix=f"flair_out_")).absolute())
            
            print("project_id",project_id)
            print("input_key",input_key)
            print("tile_id",tile_id)

            print("# 1. download input raster from S3")
            bucket=get_bucket()

                # --- download ---
            download_file(
                bucket=bucket,
                s3_path=input_key,
                local_path=str(local_input),
            )

            print(f"✔ downloaded to {local_input}")

            
            print("# 2. run FLAIR inference")

            bands, _ = resolve_bands(project_id, tile_id)

            if (bands == "IRG") and (model == "small"):
                ckpt = "../flair-models/flair_cosia_swin-small-irg_upernet_custom.ckpt"
            elif (bands == "IRG") and (model == "large"):
                ckpt = "../flair-models/flair_cosia_swin-large-irg_upernet_custom.ckpt"
            elif (bands == "RGB") and (model == "small"):
                ckpt = "../flair-models/flair_cosia_swin-small-rgb_upernet_custom.ckpt"
            elif (bands == "RGB") and (model == "large"):
                ckpt = "../flair-models/flair_cosia_swin-large-rgb_upernet_custom.ckpt"
            else:
                raise ValueError(f"Unsupported model/bands combination: model={model}, bands={bands}")

            if bands == "RGB":
                norma_task = [
                {
                    "norm_type": "custom",
                    "norm_means": [105.35, 111.31, 102.09],
                    "norm_stds": [52.36, 45.63, 44.39],
                }
            ]

            elif bands == "IRG":
                norma_task = [
                {
                    "norm_type": "custom",
                    "norm_means": [106.12, 105.35, 111.31], # Mantieni i vecchi se non vuoi cambiarli
                    "norm_stds": [40.01, 52.36, 45.63]                  # I nuovi valori che desideri
                }
            ]
                    
            if model=="large":
                model_framework= {
                        "HuggingFace": {
                            "org_model": "openmmlab/upernet-swin-large"
                        }
                    }        
            
            if model=="small":
                model_framework= {
                        "HuggingFace": {
                            "org_model": "openmmlab/upernet-swin-small"
                        }
                    } 

            if output_class=="argmax":
                output_type= "argmax"
            elif output_class=="prob":
                output_type= "class_prob"

            modify_yml={"output_name":tile_id,
                        "output_path":local_outdir,
                        "input_img_path":local_input,
                            "model_weights":ckpt,
                            "norma_task":norma_task,
                            "model_framework":model_framework,
                            "output_type":output_type,}
   
            update_yaml_config(str(r"./landcover_pipeline/template/template_flair.yml"),str(r"./landcover_pipeline/inference/flair_conf.yml"),modify_yml)

            CONFIG_FILE="./landcover_pipeline/inference/flair_conf.yml"
            
            subprocess.run(["flair-detect", "--conf", CONFIG_FILE], check=True)

            local_file_out=local_outdir+os.sep+tile_id+".tif"


            if output_s3_key:
                raster_output_name = output_s3_key
            elif output_class=="prob":
                raster_output_name = raster_output_fullname(project_id,tile_id,output_class="prob")
            else:  
                # default output_class argmax              
                raster_output_name = raster_output_fullname(project_id,tile_id)
            print("raster_output_name",raster_output_name)
            upload_file(local_file_out,bucket,raster_output_name)
            # Verify upload completed before returning.
            uploaded = False
            for _ in range(3):
                if object_exists(bucket, raster_output_name):
                    uploaded = True
                    break
                time.sleep(1)
            if not uploaded:
                raise RuntimeError(
                    f"Upload verification failed for s3://{bucket}/{raster_output_name}"
                )
            print(f"# 3. upload output raster to:{raster_output_name}")


def run_flair_single(
    project_id: str,
    input_key: str,
    tile_id: str,
    model: str,
    output_class: str = "argmax",
    output_s3_key: Optional[str] = None,
    use_gpu: Optional[bool] = None,
    batch_size: Optional[int] = None,
    num_worker: Optional[int] = None,
) -> None:
    """
    Entry point used by the pipeline: the engine is chosen by `model`.
      - "flairhub"       -> FLAIR-HUB (flairhub_zonal), template on S3
      - "small" / "large" -> FLAIR-1 (flair-detect), unchanged behaviour
    use_gpu, batch_size and num_worker apply to FLAIR-HUB only.
    """
    if model == FLAIRHUB_MODEL:
        return run_flairhub_single(
            project_id,
            input_key,
            tile_id,
            model,
            output_class=output_class,
            output_s3_key=output_s3_key,
            use_gpu=use_gpu,
            batch_size=batch_size,
            num_worker=num_worker,
        )

    if any(v is not None for v in (use_gpu, batch_size, num_worker)):
        raise ValueError(
            "use_gpu / batch_size / num_worker are supported only with "
            f"model='{FLAIRHUB_MODEL}' (got model='{model}')"
        )
    return run_flair1_single(
        project_id,
        input_key,
        tile_id,
        model,
        output_class=output_class,
        output_s3_key=output_s3_key,
    )
