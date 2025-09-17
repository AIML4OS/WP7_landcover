"""
This script converts all .ECW files in a specified folder to GeoTIFF (.TIF) format
using GDAL, with lossless compression (LZW), tiling enabled, and BigTIFF support.

IMPORTANT:
Run this script from the OSGeo4W Shell (or QGIS Python environment),
as it relies on GDAL with ECW driver support that is typically included there.

To execute the script, open the OSGeo4W Shell and run:

python conversionECW2TIF.py
"""

import os
import boto3
from osgeo import gdal
from configparser import ConfigParser
from botocore.exceptions import NoCredentialsError

# === Load configuration from IT_CONFIG.ini file ===
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, "IT_CONFIG.ini")  # Config file must be in the same folder as this script

config_object = ConfigParser()
config_object.read(os.path.realpath(config_path))

# Connection parameters for S3-like storage
connection_attribs = config_object["CONNECTION"]
ISTAT_PROXY = connection_attribs["istat_proxy"]
ACCESS_KEY = connection_attribs["access_key"]
SECRET_KEY = connection_attribs["secret_key"]
ENDPOINT_URL = connection_attribs["endpoint_url"]
BUCKET_NAME = connection_attribs["bucket_name"]

# Parameters related to conversion
ecw2tiff_attribs = config_object["ECW2TIFF"]
BAND_RGB = bool(ecw2tiff_attribs["band_rgb"]) # True → RGB mode, False → INF mode
TAG = ecw2tiff_attribs["tag"]                 # Tag used to filter filenames
RGB_INPUT_FOLDER = os.path.realpath(ecw2tiff_attribs["rgb_input_folder"])
RGB_TIF_LOCAL_FOLDER = os.path.realpath(ecw2tiff_attribs["rgb_tif_local_folder"])
INF_INPUT_FOLDER = os.path.realpath(ecw2tiff_attribs["inf_input_folder"])
INF_TIF_LOCAL_FOLDER = os.path.realpath(ecw2tiff_attribs["inf_tif_local_folder"])
RGB_REMOTE_FOLDER = ecw2tiff_attribs["rgb_remote_folder"]
INF_REMOTE_FOLDER = ecw2tiff_attribs["inf_remote_folder"]

# === Set proxy environment variables ===
os.environ['HTTP_PROXY'] = ISTAT_PROXY
os.environ['HTTPS_PROXY'] = ISTAT_PROXY

print("Starting conversion...")

# Select input/output folders based on chosen band
if BAND_RGB==True: 
    input_folder = RGB_INPUT_FOLDER
    tif_local_folder = RGB_TIF_LOCAL_FOLDER
else:
    input_folder = INF_INPUT_FOLDER
    tif_local_folder = INF_TIF_LOCAL_FOLDER  # You can change this if you want to save the output elsewhere

# === Create S3 client ===
s3 = boto3.client('s3',
                  aws_access_key_id=ACCESS_KEY,
                  aws_secret_access_key=SECRET_KEY,
                  endpoint_url=ENDPOINT_URL)

# Print visible buckets (test connection)
response = s3.list_buckets()
print("📦 Buckets visible with specified keys:")
for bucket in response['Buckets']:
    print("-", bucket['Name'])

# === Process each ECW file in the input folder ===
counts=0
for filename in os.listdir(input_folder):    
    # Only process files matching the specified TAG
    if filename.replace("w.ecw","").endswith(TAG)==False:
        continue
    counts+=1        
    print(f"Processing file: {filename}, N {counts}")

    ecw_path = os.path.join(input_folder, filename)
    output_filename = os.path.splitext(filename)[0] + ".tif"
    tif_path = os.path.join(tif_local_folder, output_filename)          

    # Define remote storage path
    if BAND_RGB==True:
        remote_path = RGB_REMOTE_FOLDER+output_filename
    else:
        remote_path = INF_REMOTE_FOLDER+output_filename       

    # === Check if file already exists in bucket ===
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=remote_path)
        print(remote_path)
        print("File already loaded → upload skipped.")
        fileToLoad=False
    except:
        print("File not yet loaded → will upload.")
        fileToLoad=True
 
    # === Convert ECW to GeoTIFF ===
    if (filename.lower().endswith(".ecw")) & fileToLoad:
        print(f"Converting: {ecw_path} -> {tif_path}")
        print("Waiting until conversion is finished...")

        try:
            gdal.Translate(
                tif_path,
                ecw_path,
                format="GTiff",
                creationOptions=[
                    "COMPRESS=LZW",        # Apply lossless compression
                    "TILED=YES",           # Enable tiling for better performance
                    "BIGTIFF=IF_SAFER"     # Allow large files if required
                ]
            )
            print("Conversion finished:",tif_path)
        except:
            print(f"Error converting: {filename}, skipped")

        # === Upload result to S3 ===
        try:
            s3.upload_file(tif_path, BUCKET_NAME, remote_path)
            print(f"Uploaded: {output_filename} → {remote_path}")
            os.remove(tif_path)
            print(f"Deleted local file: {tif_path}" ) 
        except Exception as e:
            print(f"Error uploading '{filename}': {e}")

print("All conversions completed.")


