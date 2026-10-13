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
# INPUT paths
# ----------------------------

def input_root(project_id: str) -> str:
    return f"{project_root(project_id)}/input"

def imagery_name(project_id: str,rgb: Path,model_variant:str) -> str:    
    return   f"{rgb.stem}_{model_variant}.tif"

def imagery_dir(project_id: str) -> str:
    return f"{input_root(project_id)}/imagery/"

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

def raster_output_fullname(project_id: str,tile_id: str,output_class: str="argmax") -> str:    
    outraster=raster_output_dir(project_id)
    if output_class=="prob":
        return (f"{outraster}/{tile_id}_lc"+"_prob"+".tif")
    if output_class=="argmax":
        return (f"{outraster}/{tile_id}_lc.tif")    

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

