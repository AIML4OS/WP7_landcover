# Veneto Pipeline Runbook (IT/veneto/2021)

This document lists the full pipeline sequence with short operational notes.

## 0) Environment - S3 Credentials
Set S3 variables before running the pipeline.

Linux/macOS:

```bash
export AWS_ACCESS_KEY_ID="<your-access-key>"
export AWS_SECRET_ACCESS_KEY="<your-secret-key>"
export AWS_DEFAULT_REGION="<your-region>"
export AWS_S3_ENDPOINT_URL="<your-s3-endpoint>"
export S3_BUCKET="ITS3"
```

PowerShell:

```powershell
$env:AWS_ACCESS_KEY_ID="<your-access-key>"
$env:AWS_SECRET_ACCESS_KEY="<your-secret-key>"
$env:AWS_DEFAULT_REGION="<your-region>"
$env:AWS_S3_ENDPOINT_URL="<your-s3-endpoint>"
$env:S3_BUCKET="ITS3"
```

## 1) Preprocessing
Prepare project inputs and metadata before model execution.

```powershell
python -m landcover_pipeline.cli.preprocess --project IT/veneto/2021 --rgb "<folder_rgb>" --infrared "<folder_ir>"
```

Use `--rgb` alone (3 bands, stored as `*_RGB.tif`), `--rgbi` (R,G,B,IR) or `--irgb` (IR,R,G,B)
for files that already have 4 bands. See `preprocessing_guide.md`.

## Executions (`--run`)
Imagery is stored once in the data project `IT/veneto/2021/input/imagery`. Every other stage
works on an execution, `IT/veneto/2021/execution/<run>/`, with its own template, status, outputs
and quality. Add `--run <name>` to the stage commands (or pass the extended project id
`IT/veneto/2021/execution/<name>` as `--project`; the two are equivalent).

For FLAIR-HUB the run name starts with the bands: `rgb` (reads R,G,B) or `irg` (reads IR,R,G
from the 4-band tiles). An optional label after `_` keeps executions apart, e.g. `rgb_swin` and
`rgb_convnext`. The template goes in the execution and carries the model weights:

```
IT/veneto/2021/execution/rgb_swin/input/template_flairhub_RGB.yml
IT/veneto/2021/execution/rgb_convnext/input/template_flairhub_RGB.yml
IT/veneto/2021/execution/irg/input/template_flairhub_IRG.yml
```

Output rasters inherit the run name: `execution/rgb_swin/output/raster/016092w_RGBI_rgb_swin_lc.tif`.

Tiles that a run cannot read (an `_RGB` tile with run `irg`) are skipped with a message.
FLAIR-1 (`small`/`large`) accepts any run name except those starting with `irg`. Without `--run`
the project is used as before (output `<tile>_lc.tif`).

## 2) Inference
Run land-cover model inference on imagery tiles.

```powershell
python -m landcover_pipeline.cli.inference --project IT/veneto/2021 --model small
python -m landcover_pipeline.cli.inference --project IT/veneto/2021 --run rgb --model flairhub
python -m landcover_pipeline.cli.inference --project IT/veneto/2021 --run irg --model flairhub --use-gpu true --batch-size 4
```

## 3) Vectorization
Convert raster predictions into vector outputs.

```powershell
python -m landcover_pipeline.cli.vectorize --project IT/veneto/2021
```

## 4) Build Raster Footprint
Create tile footprint used by quality crop selection.

```powershell
python -m landcover_pipeline.cli.build_raster_footprints --project IT/veneto/2021
```

## 5) Output Stats
Compute output statistics products for the project using AOI `.gpkg` and raster resolution.

```powershell
python -m landcover_pipeline.cli.compute_stats --project IT/veneto/2021 --aoi "veneto2021.gpkg" --resolution 0.2
```

## 6) Quality - Crop Tiles
Select LUCAS points in AOI and generate point-centered crops.

```powershell
python -m landcover_pipeline.cli.quality_crop --project IT/veneto/2021 --lucas-csv "landcover_pipeline/Pipeline code for accuracy assessment/IT_LUCAS_2022.csv" --aoi "veneto2021.gpkg" --crop-size 2176
```

## 7) Quality - Probabilities
Run FLAIR probabilities on crop tiles and upload to S3.

```powershell
python -m landcover_pipeline.cli.quality_probabilities --project IT/veneto/2021 --crop-size 2176 --model small
```

Optional: run only a random sample of missing crops.

```powershell
python -m landcover_pipeline.cli.quality_probabilities --project IT/veneto/2021 --crop-size 2176 --model small --nsample 100
```

## 8) Quality - Coordinate Conversion
Convert LUCAS coordinates to projected CRS used for extraction.

```powershell
python -m landcover_pipeline.cli.quality_convert_coords --epsg EPSG:32632 --nuts2 ITH3 --input-file "landcover_pipeline/Pipeline code for accuracy assessment/IT_LUCAS_2022.csv" --modality LUCAS
```

## 9) Quality - Predictions Extraction
Extract probability band values at converted point coordinates.

```powershell
python -m landcover_pipeline.cli.quality_extract_predictions --project IT/veneto/2021 --crop-size 2176 --coord-file "landcover_pipeline/Pipeline code for accuracy assessment/IT_LUCAS_2022_ITH3_EPSG32632.txt" --output-folder "landcover_pipeline/Pipeline code for accuracy assessment"
```

## 10) Quality - Accuracy Assessment
Compute quality metrics from extracted predictions.

```powershell
python -m landcover_pipeline.cli.quality_accuracy_measures --predictions-file "landcover_pipeline/Pipeline code for accuracy assessment/predictions_IT_veneto_2021_crop2176.txt"
```
