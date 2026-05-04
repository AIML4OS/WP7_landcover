"""
Input preparation and harmonisation for the Land Cover Pipeline.

Supports RGB, RGBI / IRGB and RGB + IR inputs.
All outputs are written as GeoTIFFs compatible with the selected model.
"""

from pathlib import Path
from typing import List, Optional

SUPPORTED_MODEL_VARIANTS = {"RGB", "IRG"}


# -----------------------------------------------------
# Low-level raster operations (to be implemented)
# -----------------------------------------------------


from osgeo import gdal

def _infer_band_layout(band_count: int, color_interps: list[str]) -> str:
    """
    Infer band layout from band count and color interpretation.
    """

    ci = [c.upper() if c else "" for c in color_interps]

    if band_count == 3:
        if ci == ["RED", "GREEN", "BLUE"]:
            return "RGB"
        return "UNKNOWN_3B"

    if band_count == 4:
        if "RED" in ci and "GREEN" in ci and "BLUE" in ci:
            return "RGBI"   # could be RGBI or IRGB
        return "UNKNOWN_4B"

    return "UNKNOWN"



def read_band_info(raster_path: str) -> dict:
    """
    Read band information from a raster file using GDAL.

    Returns a dictionary with:
    - band_count
    - band_descriptions
    - color_interpretations
    - detected_layout
    """
    gdal.UseExceptions()
    ds = gdal.Open(raster_path)
    if ds is None:
        raise RuntimeError(f"Unable to open raster: {raster_path}")

    band_count = ds.RasterCount

    band_descriptions = []
    color_interpretations = []

    for i in range(1, band_count + 1):
        band = ds.GetRasterBand(i)

        desc = band.GetDescription()
        band_descriptions.append(desc if desc else None)

        color_interp = band.GetColorInterpretation()
        color_interpretations.append(
            gdal.GetColorInterpretationName(color_interp)
        )

    detected_layout = _infer_band_layout(band_count, color_interpretations)

    return {
        "band_count": band_count,
        "band_descriptions": band_descriptions,
        "color_interpretations": color_interpretations,
        "detected_layout": detected_layout,
    }


def select_bands(
    src: Path,
    band_indices: List[int],
    dst: Path,
) -> Path:
    """
    Select specific bands from a raster (ECW or TIF)
    and write a GeoTIFF.
    """
    raise NotImplementedError


def merge_rgb_ir(
    rgb: Path,
    ir: Path,
    dst: Path,
) -> Path:
    """
    Merge RGB raster and IR raster into a single IRG GeoTIFF.
    """
    raise NotImplementedError

from pathlib import Path
from typing import List, Optional

from osgeo import gdal

SUPPORTED_MODEL_VARIANTS = {"RGB", "IRG"}


def _get_rgb_band_indices(color_interps: List[str]) -> List[int]:
    """
    Return band indices (1-based) corresponding to RGB bands.
    """
    rgb_map = {"RED": None, "GREEN": None, "BLUE": None}

    for idx, ci in enumerate(color_interps, start=1):
        ci = ci.upper()
        if ci in rgb_map and rgb_map[ci] is None:
            rgb_map[ci] = idx

    if None in rgb_map.values():
        raise ValueError("Unable to identify RGB bands from color interpretation")

    return [rgb_map["RED"], rgb_map["GREEN"], rgb_map["BLUE"]]


def _get_ir_band_index(color_interps: List[str]) -> int:
    """
    Return band index (1-based) for infrared band.
    Fallback: assume the remaining band in a 4-band raster.
    """
    known = {"RED", "GREEN", "BLUE"}
    candidates = []

    for idx, ci in enumerate(color_interps, start=1):
        if ci.upper() not in known:
            candidates.append(idx)

    if len(candidates) != 1:
        raise ValueError("Unable to uniquely identify infrared band")

    return candidates[0]


def select_bands(src: Path, band_indices: List[int], dst: Path) -> Path:
    """
    Select bands from a raster and write a GeoTIFF.
    """
    translate_opts = gdal.TranslateOptions(
        bandList=band_indices,
        format="GTiff",
    )

    result = gdal.Translate(str(dst), str(src), options=translate_opts)
    if result is None:
        raise RuntimeError(f"GDAL band selection failed for {src}")

    return dst


def merge_rgb_ir(rgb: Path, ir: Path, dst: Path) -> Path:
    """
    Merge RGB raster (3 bands) and IR raster (1 band) into IRG GeoTIFF.
    """
    vrt_path = dst.with_suffix(".vrt")

    vrt = gdal.BuildVRT(
        str(vrt_path),
        [str(rgb), str(ir)],
        separate=True,
    )
    if vrt is None:
        raise RuntimeError("GDAL VRT build failed")

    result = gdal.Translate(str(dst), vrt, format="GTiff")
    if result is None:
        raise RuntimeError("GDAL merge failed")

    vrt_path.unlink(missing_ok=True)
    return dst


def prepare_inputs(
    rgb_files: List[Path],
    ir_files: Optional[List[Path]],
    model_variant: str,
    work_dir: Path,
) -> List[Path]:

    if model_variant not in SUPPORTED_MODEL_VARIANTS:
        raise ValueError(f"Unsupported model variant: {model_variant}")

    prepared_files: List[Path] = []

    for idx, rgb in enumerate(rgb_files):
        info = read_band_info(rgb)
        n_bands = info["band_count"]
        color_interps = info["color_interpretations"]

        out_name = rgb.stem + f"_{model_variant}.tif"
        out_path = work_dir / out_name

        # ---------------------------------
        # MODEL: RGB
        # ---------------------------------
        if model_variant == "RGB":

            if n_bands == 3:
                # RGB → pass-through (rewrite as GeoTIFF)
                select_bands(rgb, [1, 2, 3], out_path)

            elif n_bands == 4:
                # RGBI / IRGB → select RGB
                rgb_indices = _get_rgb_band_indices(color_interps)
                select_bands(rgb, rgb_indices, out_path)

            else:
                raise ValueError(
                    f"Unsupported number of bands ({n_bands}) for RGB model"
                )

        # ---------------------------------
        # MODEL: IRG
        # ---------------------------------
        elif model_variant == "IRG":

            if n_bands == 4:
                # RGBI / IRGB → select IRG
                rgb_indices = _get_rgb_band_indices(color_interps)
                ir_index = _get_ir_band_index(color_interps)
                select_bands(rgb, [ir_index] + rgb_indices, out_path)

            elif ir_files:
                # RGB (3b) + separate IR
                ir = ir_files[idx]
                merge_rgb_ir(rgb, ir, out_path)

            else:
                raise ValueError(
                    "IRG model requires either RGBI/IRGB inputs "
                    "or a separate infrared folder."
                )

        prepared_files.append(out_path)

    return prepared_files



def prepare_single_input(
    rgb: Path,
    ir: Optional[Path],
    model_variant: str,
    out_path=str,
) -> Path:
    """
    Prepare a single raster input according to model requirements.
    Always writes a GeoTIFF.

    Returns
    -------
    Path
        Path to prepared GeoTIFF.
    """


    info = read_band_info(rgb)
    n_bands = info["band_count"]
    color_interps = info["color_interpretations"]


    # -----------------------------
    # MODEL: RGB
    # -----------------------------
    if model_variant == "RGB":

        if n_bands == 3:
            # RGB → rewrite as GeoTIFF
            select_bands(rgb, [1, 2, 3], out_path)

        elif n_bands == 4:
            # RGBI / IRGB → select RGB
            rgb_indices = _get_rgb_band_indices(color_interps)
            select_bands(rgb, rgb_indices, out_path)

        else:
            raise ValueError(
                f"Unsupported number of bands ({n_bands}) for RGB model"
            )

    # -----------------------------
    # MODEL: IRG
    # -----------------------------
    elif model_variant == "IRG":

        if n_bands == 4:
            # RGBI / IRGB → select IRG
            rgb_indices = _get_rgb_band_indices(color_interps)
            ir_index = _get_ir_band_index(color_interps)
            select_bands(rgb, [ir_index] + rgb_indices, out_path)

        elif ir is not None:
            # RGB + IR separate
            merge_rgb_ir(rgb, ir, out_path)

        else:
            raise ValueError(
                "IRG model requires either RGBI/IRGB inputs "
                "or a separate infrared file."
            )

    else:
        raise ValueError(f"Unsupported model variant: {model_variant}")

    return out_path
