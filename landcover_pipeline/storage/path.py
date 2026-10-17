"""
S3 path conventions for the Land Cover Pipeline.

Project identifier (<COUNTRY>/<REGION>/<DATE>) is the root namespace.
All pipeline components must use these helpers.
"""
from pathlib import Path
from typing import Optional

# ----------------------------
# Project root
# ----------------------------

def project_root(project_id: str) -> str:
    """
    Example:
        IT/Veneto/2021
    """
    return project_id.strip("/")


# ----------------------------
# Executions
#
# A project holds the imagery once (<project>/input/imagery) and any number of
# executions (<project>/execution/<run>) with their own template, status,
# output and quality. An execution is addressed with the extended project id
# <project>/execution/<run>: every stage works on it as on a plain project,
# only the imagery is always read from the data project.
# ----------------------------

EXECUTION_DIR = "execution"


def execution_project_id(project_id: str, run: Optional[str] = None) -> str:
    """
    Example:
        execution_project_id("IT/veneto/2021", "rgb") -> IT/veneto/2021/execution/rgb
        execution_project_id("IT/veneto/2021")        -> IT/veneto/2021
    """
    root = project_root(project_id)
    if run is None:
        return root
    run = run.strip("/")
    if not run or "/" in run:
        raise ValueError(f"Invalid run name: {run!r}")
    if run_name(root) is not None:
        raise ValueError(f"{root} is already an execution: do not combine it with a run")
    return f"{root}/{EXECUTION_DIR}/{run}"


def data_project_id(project_id: str) -> str:
    """Data project of a project or execution id: IT/veneto/2021/execution/rgb -> IT/veneto/2021"""
    root = project_root(project_id)
    return root.split(f"/{EXECUTION_DIR}/")[0]


def run_name(project_id: str) -> Optional[str]:
    """Run of an execution id (rgb), None for a plain project id."""
    root = project_root(project_id)
    if f"/{EXECUTION_DIR}/" not in root:
        return None
    return root.split(f"/{EXECUTION_DIR}/", 1)[1]


# ----------------------------
# INPUT paths
# ----------------------------

def input_root(project_id: str) -> str:
    return f"{project_root(project_id)}/input"

def imagery_name(project_id: str,rgb: Path,model_variant:str) -> str:    
    return   f"{rgb.stem}_{model_variant}.tif"

def imagery_dir(project_id: str) -> str:
    # imagery always lives in the data project, also for an execution id
    return f"{input_root(data_project_id(project_id))}/imagery/"

def master_config_path(project_id: str) -> str:
    return f"{input_root(project_id)}/config_master.yml"

def flairhub_template_path(project_id: str, variant: str) -> str:
    """
    Example:
        IT/veneto/2021/input/template_flairhub_IRG.yml
    """
    return f"{input_root(project_id)}/template_flairhub_{variant}.yml"

def footprint_path(project_id: str) -> str:
    return f"{input_root(project_id)}/footprint.gpkg"

# ----------------------------
# STATUS paths
# ----------------------------


def status_dir(project_id: str, stage: str) -> str:
    return f"{project_id}/status_{stage}"


#def status_vector_dir(project_id: str) -> str:
#    return f"{project_id}/status_vector/"


def tile_status_path(project_id: str, tile_id: str, status: str) -> str:
    """
    Example:
        IT/Veneto/2021/status/tile_012.done
    """
    return f"{status_dir(project_id)}/{tile_id}.{status}"


# ----------------------------
# OUTPUT paths
# ----------------------------

def output_root(project_id: str) -> str:
    return f"{project_root(project_id)}/output"


def raster_output_dir(project_id: str) -> str:
    return f"{output_root(project_id)}/raster"

def raster_output_name(project_id: str, tile_id: str) -> str:
    """
    Tile name used for the output raster. In an execution the file inherits
    the run name, so files of different runs stay distinguishable after download:
        IT/veneto/2021/execution/rgb_swin, 016092w_RGBI -> 016092w_RGBI_rgb_swin
        IT/veneto/2021 (no run)                         -> 016092w_RGB
    """
    run = run_name(project_id)
    return f"{tile_id}_{run}" if run else tile_id


def tile_id_from_output(project_id: str, name: str) -> str:
    """Inverse of raster_output_name (output file name or stem -> imagery tile id)."""
    name = Path(str(name)).stem
    if name.endswith("_lc"):
        name = name[:-3]
    run = run_name(project_id)
    if run and name.endswith(f"_{run}"):
        name = name[: -len(run) - 1]
    return name


def raster_output_fullname(project_id: str,tile_id: str,output_class: str="argmax") -> str:    
    outraster=raster_output_dir(project_id)
    name=raster_output_name(project_id, tile_id)
    if output_class=="prob":
        return (f"{outraster}/{name}_lc"+"_prob"+".tif")
    if output_class=="argmax":
        return (f"{outraster}/{name}_lc.tif")    

def vector_output_dir(project_id: str) -> str:
    return f"{output_root(project_id)}/vector"


# ----------------------------
# QUALITY paths
# ----------------------------


def quality_root(project_id: str) -> str:
    return f"{project_root(project_id)}/quality"

def quality_work_dir(project_id: str) -> str:
    """
    Example:
        IT/Veneto/2021/quality/work_dir
    """
    return f"{quality_root(project_id)}/work_dir"

def quality_probability_dir(project_id: str, crop_size: int, model: Optional[str] = None) -> str:
    """
    Example:
        IT/Veneto/2021/quality/probability/600_small
    """
    folder = str(int(crop_size))
    if model:
        folder = f"{folder}_{model}"
    return f"{quality_root(project_id)}/probability/{folder}"

def quality_probability_path(project_id: str, crop_size: int, tile_id: str, model: Optional[str] = None) -> str:
    return f"{quality_probability_dir(project_id, crop_size, model=model)}/{tile_id}.tif"


def quality_report_path(project_id: str, name: str) -> str:
    """
    Example:
        IT/Veneto/2021/quality/accuracy_metrics.json
    """
    return f"{quality_root(project_id)}{name}"


# ----------------------------
# STATS paths
# ----------------------------
def stats_root(project_id: str) -> str:
    return f"{output_root(project_id)}/stats"

def landcover_stats_path(project_id: str, aio_name) -> str:
    filename = aio_name+"_stats.csv"
    return f"{stats_root(project_id)}/{filename}"

def landcover_overlap_path(project_id: str, aio_name) -> str:
    filename = aio_name+"_overlap_tiles.gpkg"
    return f"{stats_root(project_id)}/{filename}"

def landcover_overlap_aoi_path(project_id: str, aio_name) -> str:
    filename = aio_name+"_overlap_tiles_aoi.gpkg"
    return f"{stats_root(project_id)}/{filename}"

