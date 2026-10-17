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


# =====================================================================
# Content-based preparation (no model variant)
#
# Imagery is stored in S3 by what it contains, not by the model that will
# read it:
#     <tile>_RGB.tif    3 bands  R,G,B
#     <tile>_RGBI.tif   4 bands  R,G,B,IR   (canonical order)
# Which bands a model reads (RGB or IRG) is decided at inference time.
# =====================================================================

from dataclasses import dataclass

# input kind -> (bands read from the source, output content)
#   rgb  : source has 3 bands R,G,B   (optionally paired with a 1-band IR file)
#   rgbi : source has 4 bands R,G,B,IR
#   irgb : source has 4 bands IR,R,G,B  (reordered to R,G,B,IR)
INPUT_KINDS = ("rgb", "rgbi", "irgb")

_KNOWN_SUFFIXES = ("_RGBI", "_IRGB", "_RGB", "_IRG")

_BAND_ORDER = {          # source band indices (1-based) -> canonical R,G,B(,IR)
    "rgb": [1, 2, 3],
    "rgbi": [1, 2, 3, 4],
    "irgb": [2, 3, 4, 1],
}
_EXPECTED_BANDS = {"rgb": 3, "rgbi": 4, "irgb": 4}


def tile_stem(path: Path) -> str:
    """File name without extension and without a known band suffix."""
    stem = Path(path).stem
    for suffix in _KNOWN_SUFFIXES:
        if stem.upper().endswith(suffix):
            return stem[: -len(suffix)]
    return stem


@dataclass(frozen=True)
class PreprocessJob:
    src: Path                 # RGB, RGBI or IRGB source
    kind: str                 # "rgb" | "rgbi" | "irgb"
    ir: Optional[Path]        # separate 1-band IR file (kind == "rgb" only)

    @property
    def stem(self) -> str:
        return tile_stem(self.src)

    @property
    def content(self) -> str:
        """Content of the file that will be stored: "RGB" or "RGBI"."""
        return "RGB" if self.kind == "rgb" and self.ir is None else "RGBI"

    @property
    def out_name(self) -> str:
        return f"{self.stem}_{self.content}.tif"


def pair_by_name(rgb_files: List[Path], ir_files: List[Path]) -> List[tuple]:
    """
    Pair RGB and IR files by file name (extension and known band suffix
    ignored, case-insensitive). Any unmatched or duplicated name is an error.
    """
    def index(files, label):
        out, dup = {}, []
        for f in files:
            key = tile_stem(f).lower()
            if key in out:
                dup.append(f"{out[key]} / {f}")
            out[key] = f
        if dup:
            raise ValueError(f"Duplicate {label} tile names: " + "; ".join(dup))
        return out

    rgb_idx = index(rgb_files, "RGB")
    ir_idx = index(ir_files, "infrared")

    only_rgb = sorted(set(rgb_idx) - set(ir_idx))
    only_ir = sorted(set(ir_idx) - set(rgb_idx))
    if only_rgb or only_ir:
        msg = []
        if only_rgb:
            msg.append(f"{len(only_rgb)} RGB tile(s) without infrared: {only_rgb[:10]}")
        if only_ir:
            msg.append(f"{len(only_ir)} infrared tile(s) without RGB: {only_ir[:10]}")
        raise ValueError("; ".join(msg))

    return [(rgb_idx[k], ir_idx[k]) for k in sorted(rgb_idx)]


def plan_jobs(
    rgb_files: List[Path] = (),
    rgbi_files: List[Path] = (),
    irgb_files: List[Path] = (),
    ir_files: Optional[List[Path]] = None,
) -> List[PreprocessJob]:
    """
    Build the list of jobs from the scanned folders.
    Raises ValueError for: no input, --infrared without --rgb, unmatched
    RGB/IR pairs, or two sources producing the same output file name.
    """
    if not (rgb_files or rgbi_files or irgb_files):
        raise ValueError("No input files: give at least one of rgb, rgbi, irgb")
    if ir_files and not rgb_files:
        raise ValueError("Infrared files can only be combined with RGB (3-band) files")

    jobs: List[PreprocessJob] = []
    if ir_files:
        jobs += [PreprocessJob(r, "rgb", i) for r, i in pair_by_name(rgb_files, ir_files)]
    else:
        jobs += [PreprocessJob(f, "rgb", None) for f in rgb_files]
    jobs += [PreprocessJob(f, "rgbi", None) for f in rgbi_files]
    jobs += [PreprocessJob(f, "irgb", None) for f in irgb_files]

    seen = {}
    for job in jobs:
        key = job.out_name.lower()
        if key in seen:
            raise ValueError(
                f"Two sources produce the same output {job.out_name}: "
                f"{seen[key].src} and {job.src}"
            )
        seen[key] = job
    return jobs


def check_job(job: PreprocessJob) -> None:
    """
    Cheap metadata check (no pixel reading): band count, 8-bit data and,
    for RGB+IR pairs, same size and georeferencing.
    """
    gdal.UseExceptions()

    def open_info(path):
        ds = gdal.Open(str(path))
        if ds is None:
            raise ValueError(f"Unable to open {path}")
        return ds

    ds = open_info(job.src)
    expected = _EXPECTED_BANDS[job.kind]
    if ds.RasterCount != expected:
        raise ValueError(
            f"{job.src}: expected {expected} bands for '{job.kind}', "
            f"found {ds.RasterCount}"
        )
    for i in range(1, ds.RasterCount + 1):
        dtype = gdal.GetDataTypeName(ds.GetRasterBand(i).DataType)
        if dtype != "Byte":
            raise ValueError(f"{job.src}: band {i} is {dtype}, 8-bit (Byte) expected")

    if job.ir is not None:
        ir = open_info(job.ir)
        if ir.RasterCount != 1:
            raise ValueError(f"{job.ir}: infrared file must have 1 band, found {ir.RasterCount}")
        if gdal.GetDataTypeName(ir.GetRasterBand(1).DataType) != "Byte":
            raise ValueError(f"{job.ir}: infrared band must be 8-bit (Byte)")
        same_size = (ds.RasterXSize, ds.RasterYSize) == (ir.RasterXSize, ir.RasterYSize)
        gt_a, gt_b = ds.GetGeoTransform(), ir.GetGeoTransform()
        same_geo = all(abs(a - b) < 1e-6 for a, b in zip(gt_a, gt_b))
        if not (same_size and same_geo):
            raise ValueError(
                f"{job.src} and {job.ir} differ in size or georeferencing"
            )


def prepare_job(job: PreprocessJob, out_path: Path) -> Path:
    """
    Write the GeoTIFF for one job: R,G,B (RGB) or R,G,B,IR (RGBI).
    """
    out_path = Path(out_path)
    if job.ir is not None:
        merge_rgb_ir(job.src, job.ir, out_path)      # R,G,B + IR -> R,G,B,IR
    else:
        select_bands(job.src, _BAND_ORDER[job.kind], out_path)

    # canonical band labels (the source 4th band may be tagged Alpha/Gray/...)
    labels = [("R", gdal.GCI_RedBand), ("G", gdal.GCI_GreenBand),
              ("B", gdal.GCI_BlueBand), ("IR", gdal.GCI_GrayIndex)]
    ds = gdal.Open(str(out_path), gdal.GA_Update)
    for i in range(1, ds.RasterCount + 1):
        name, interp = labels[i - 1]
        band = ds.GetRasterBand(i)
        band.SetColorInterpretation(interp)
        band.SetDescription(name)
    ds.FlushCache()
    ds = None
    return out_path
