# inference/flairhub.py
import time
from pathlib import Path
from typing import Optional
from ruamel.yaml import YAML
from landcover_pipeline.template.yml_config import update_yaml_config
from landcover_pipeline.storage.s3 import download_file, get_bucket, object_exists, upload_file
from landcover_pipeline.storage.path import raster_output_fullname, flairhub_template_path
from landcover_pipeline.inference.bands import resolve_bands
import tempfile
import subprocess

# Reported in the log for every tile, so a run can be traced back to its settings.
LOGGED_PARAMS = (
    "use_gpu",
    "batch_size",
    "num_worker",
    "margin",
    "img_pixels_detection",
    "output_px_meters",
)


def _load_yaml(path) -> dict:
    with open(path, "r") as f:
        return YAML(typ="safe").load(f)


def _input_modality(template: dict) -> str:
    """Name of the single input modality switched on in the template."""
    inputs = template["modalities"]["inputs"]
    active = [name for name, on in inputs.items() if on]
    if len(active) != 1:
        raise ValueError(
            f"Template must activate exactly one input modality, found: {active}"
        )
    return active[0]


def _find_output(out_dir: Path, output_type: str) -> Path:
    """The single raster written by FLAIR-HUB for the requested output type."""
    found = [p for p in out_dir.rglob("*.tif") if output_type in p.name]
    if len(found) != 1:
        listing = sorted(
            str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()
        )
        raise RuntimeError(
            f"Expected exactly one '{output_type}' raster in {out_dir}, found: {listing}"
        )
    return found[0]


def run_flairhub_single(
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
    Runs FLAIR-HUB on a single input raster.

    The run configuration is the template stored on S3 in the project
    (<project>/input/template_flairhub_<RGB|IRG>.yml). With an execution
    project id (<project>/execution/<rgb|irg>) the run decides the bands and
    the code sets the channels of the input modality ([1,2,3] or [4,1,2]);
    with a plain project the variant comes from the tile id and the channels
    stay those of the template. Paths and output type are written by the code;
    use_gpu, batch_size and num_worker override the template when given.
    `model` is kept as a label only.
    """
    variant, channels = resolve_bands(project_id, tile_id)
    output_type = {"argmax": "argmax", "prob": "class_prob"}[output_class]

    bucket = get_bucket()
    template_key = flairhub_template_path(project_id, variant)
    if not object_exists(bucket, template_key):
        raise FileNotFoundError(
            f"FLAIR-HUB template not found: s3://{bucket}/{template_key}"
        )

    with tempfile.TemporaryDirectory(prefix=f"flair_{tile_id}_") as work_dir:
        with tempfile.TemporaryDirectory(prefix="flair_out_") as local_outdir:
            work_dir = Path(work_dir)
            local_outdir = Path(local_outdir)

            print("project_id", project_id)
            print("input_key", input_key)
            print("tile_id", tile_id)

            print("# 1. download input raster and template from S3")
            local_input = work_dir / f"{tile_id}.tif"
            local_template = work_dir / "template.yml"

            download_file(
                bucket=bucket,
                s3_path=input_key,
                local_path=str(local_input),
            )
            download_file(
                bucket=bucket,
                s3_path=template_key,
                local_path=str(local_template),
            )

            print(f"✔ downloaded to {local_input}")

            print("# 2. run FLAIR-HUB inference")

            template = _load_yaml(local_template)
            modality = _input_modality(template)

            modality_cfg = {"input_img_path": str(local_input)}
            if channels is not None:
                if "channels" not in (template["modalities"].get(modality) or {}):
                    raise ValueError(
                        f"Template modality {modality} has no 'channels' key: "
                        f"add it (the run sets it to {channels})"
                    )
                modality_cfg["channels"] = channels

            modify_yml = {
                "output_name": tile_id,
                "output_path": str(local_outdir),
                "output_type": output_type,
                "modalities": {modality: modality_cfg},
            }
            runtime = {
                "use_gpu": use_gpu,
                "batch_size": batch_size,
                "num_worker": num_worker,
            }
            modify_yml.update({k: v for k, v in runtime.items() if v is not None})

            conf_file = work_dir / "flairhub_conf.yml"
            update_yaml_config(str(local_template), str(conf_file), modify_yml)

            effective = _load_yaml(conf_file)
            print("config:", {k: effective.get(k) for k in LOGGED_PARAMS})
            print("bands:", variant, "channels:", effective["modalities"][modality].get("channels"))

            subprocess.run(["flairhub_zonal", "--config", str(conf_file)], check=True)

            local_file_out = _find_output(local_outdir, output_type)

            if output_s3_key:
                raster_output_name = output_s3_key
            elif output_class == "prob":
                raster_output_name = raster_output_fullname(project_id, tile_id, output_class="prob")
            else:
                # default output_class argmax
                raster_output_name = raster_output_fullname(project_id, tile_id)
            print("raster_output_name", raster_output_name)
            upload_file(str(local_file_out), bucket, raster_output_name)
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
