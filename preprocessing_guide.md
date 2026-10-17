# WP7 Land Cover – Preprocessing Guide

> **Where to run this guide:**  
> All steps below must be executed on the **local machine where the NSO orthophotos are stored**.  
> This is not the remote CREODIAS VM — it is the local workstation that has direct access to the orthophoto files.

---

## 1. Clone the Repository

```bash
git clone https://github.com/AIML4OS/WP7_landcover.git
cd WP7_landcover
```

---

## 2. Create the Conda Environment

```bash
conda create -n landcover python=3.10
conda activate landcover
conda install -c conda-forge gdal
conda install boto3
conda install pyaml
```

---

## 3. Set S3 Credentials

Run these commands in your terminal before launching the pipeline.  
Replace `...` with your actual credentials and `<your bucket name>` with your bucket.

```bat
set AWS_ACCESS_KEY_ID=...
set AWS_SECRET_ACCESS_KEY=...
set AWS_S3_ENDPOINT_URL=https://s3.waw3-2.cloudferro.com
set AWS_S3_ENDPOINT=s3.waw3-2.cloudferro.com
set S3_BUCKET=<your bucket name>
```

> **Note:** These variables are valid for the current terminal session only.

---

## 4. Run Preprocessing

The project is identified by `<country>/<region>/<year>` (e.g. `IT/veneto/2021`).
Imagery is stored **by content**, not by model: `<tile>_RGB.tif` (3 bands R,G,B) or
`<tile>_RGBI.tif` (4 bands R,G,B,IR). Whether a model reads RGB or IRG is decided
later, at inference time.

```bash
# RGB only
python -m landcover_pipeline.cli.preprocess --project IT/veneto/2021 --rgb "..\path\to\RGB"

# RGB + separate infrared folder (paired by file name)
python -m landcover_pipeline.cli.preprocess --project IT/veneto/2021 --rgb "..\RGB" --infrared "..\IR"

# files that already have 4 bands
python -m landcover_pipeline.cli.preprocess --project IT/veneto/2021 --rgbi "..\RGBI"   # R,G,B,IR
python -m landcover_pipeline.cli.preprocess --project IT/veneto/2021 --irgb "..\IRGB"   # IR,R,G,B (reordered)
```

| Argument      | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| `--project`   | Project id `<country>/<region>/<year>`                                      |
| `--rgb`       | Folder with 3-band R,G,B orthophotos -> `*_RGB.tif` (`*_RGBI.tif` with `--infrared`) |
| `--rgbi`      | Folder with 4-band R,G,B,IR orthophotos -> `*_RGBI.tif`                     |
| `--irgb`      | Folder with 4-band IR,R,G,B orthophotos -> `*_RGBI.tif` (bands reordered)   |
| `--infrared`  | Folder with 1-band infrared orthophotos, paired by file name with `--rgb`   |

At least one of `--rgb`, `--rgbi`, `--irgb` is required and they can be combined.
Rules checked **before** anything is uploaded: every file must be 8-bit with the expected
number of bands, every `--rgb` tile must have an infrared file with the same name (and the
same size and georeferencing), and two sources must not produce the same output name.

### Expected Output

```
▶ Project ID: IT/Test/2021
▶ Target bucket: ITS3
▶ Checking S3 credentials
▶ Scanning inputs
▶ Checking 1 input file(s)
▶ Starting streaming preprocessing
▶ Processing file 1/1: 634511.tif -> 634511_RGB.tif
⬆ Uploading 634511_RGB.tif to IT/Test/2021/input/imagery/634511_RGB.tif
✔ Processed and uploaded 1 files
```

Files are uploaded to `<bucket>/<country>/<region>/<year>/input/imagery/`.
Tiles already present in S3 are skipped.
