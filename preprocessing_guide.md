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

## 4. Create the Project Configuration File

Create a file named `configLC.yml` in the `WP7_landcover` folder:

```yaml
# =====================================================
# Land Cover Pipeline – Master Configuration (v1)
# WP7 / AIML4OS
# =====================================================

project:
  country: IT
  region: Test
  year: 2021
  description: >
    Demo land cover classification based on orthophotos
    processed within the WP7 land cover pipeline.

model:
  framework: FLAIR
  task: land_cover
  variant: RGB    # RGB | IRG
```

---

## 5. Run Preprocessing

```bash
python -m landcover_pipeline.cli.preprocess \
    --config .\configLC.yml \
    --rgb    "..\path\to\RGB"
```

| Argument      | Description                                      |
|---------------|--------------------------------------------------|
| `--config`    | Path to the `configLC.yml` configuration file    |
| `--rgb`       | Folder containing RGB orthophoto files (`.tif`)  |
| `--infrared`  | *(Optional)* Folder containing infrared images   |

### Expected Output

```
▶ Loading master configuration
▶ Project ID: IT/Test/2021
▶ Model variant: RGB
▶ Target bucket: ITS3
▶ Checking S3 credentials
▶ Scanning RGB inputs
▶ Starting streaming preprocessing
▶ Processing file 1/1: 634511.tif
⬆ Uploading 634511_RGB.tif to IT/Test/2021/input/imagery/634511_RGB.tif
✔ Processed and uploaded 1 files
```

The script processes **all `.tif` files** found in the RGB folder and uploads them to S3 under the path `<bucket>/<country>/<region>/<year>/input/imagery/`.
