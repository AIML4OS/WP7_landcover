import boto3
import os
import time
from datetime import datetime
from configparser import ConfigParser

# === Load configuration from AIML4OS.ini file ===
base_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(base_dir, "AIML4OS.ini")  # Config file must be in the same folder as this script

config_object = ConfigParser()
config_object.read(os.path.realpath(config_path))

# Connection parameters
connection_attribs = config_object["CONNECTION"]
ACCESS_KEY = connection_attribs["access_key"]
SECRET_KEY = connection_attribs["secret_key"]
ENDPOINT_URL = connection_attribs["endpoint_url"]
BUCKET_NAME = connection_attribs["bucket_name"]

# Process parameters
process_attrib = config_object["PROCESS"]
LOCAL_DIR = process_attrib["local_dir"]
BAND = process_attrib["band"] # Can be: RGB or IRG
RGB_BUCKET_FOLDER_OUTPUT = process_attrib["rgb_bucket_folder_output"]
IRG_BUCKET_FOLDER_OUTPUT = process_attrib["irg_bucket_folder_output"]

# Conversion folders
ecw2tiff_attribs = config_object["ECW2TIFF"]
RGB_REMOTE_FOLDER = ecw2tiff_attribs["rgb_remote_folder"]
INF_REMOTE_FOLDER = ecw2tiff_attribs["inf_remote_folder"]

# Select correct folders depending on band
if BAND=="RGB":
    bucketFolderInput=RGB_REMOTE_FOLDER
    bucketFolderOutput=RGB_BUCKET_FOLDER_OUTPUT
if BAND=="IRG":
    bucketFolderInput=INF_REMOTE_FOLDER
    bucketFolderOutput=IRG_BUCKET_FOLDER_OUTPUT

# === Function to update YAML configuration files ===
def update_yaml(tagname):
    def update_yaml_text(key, new_value,file_yaml_input,file_yaml_output):
        # Ensure string values are quoted
        if isinstance(new_value, str) and not (new_value.startswith('"') or new_value.startswith("'")):
            new_value = f'"{new_value}"'

        # Read template file and replace values
        lines_out = []
        with open(file_yaml_input, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}:"):
                    lines_out.append(f'{key}: {new_value}\n')
                else:
                    lines_out.append(line)

        # Write updated file
        with open(file_yaml_output, "w", encoding="utf-8") as f:
            f.writelines(lines_out)

    # Paths for yaml and input/output tif
    yamlfile="./configs/"+tagname+".yaml"
    inputfile="../tryout/"+tagname+".tif"
    outputfile=tagname+".tif"

    # Update specific fields
    update_yaml_text( "output_name", outputfile,"proto.yaml",yamlfile)
    update_yaml_text( "input_img_path", inputfile,yamlfile,yamlfile)

# === Connect to S3 service ===
s3 = boto3.client('s3',
                  aws_access_key_id=ACCESS_KEY,
                  aws_secret_access_key=SECRET_KEY,
                  endpoint_url=ENDPOINT_URL)

# Print available buckets
response = s3.list_buckets()
print(" Buckets visible with specified keys:")
for bucket in response['Buckets']:
    print("-", bucket['Name'])

# List available objects inside the selected input folder
response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=bucketFolderInput)

if 'Contents' in response:
    for obj in response['Contents']:
        t0 = datetime.now()
        key = obj['Key']  # File path inside the bucket
        filename = os.path.basename(key)
        print(filename)

        # Skip folders or invalid entries
        if not filename:
            continue

        # === Download file locally ===
        local_path = os.path.join(LOCAL_DIR, filename)
        print(f"Downloading {key} -> {local_path}")
        s3.download_file(BUCKET_NAME, key, local_path)

        # === Update YAML file for processing ===
        tagname=filename.replace(".tif","")
        update_yaml(tagname)

        yamlfile="./configs/"+tagname+".yaml"
        osCommand="/home/eouser/usecase/FLAIR-1/flair-detection.sh "+yamlfile

        # Execute external shell command
        if os.system(osCommand)!=0:
            print("error")
            exit(1)

        # Measure elapsed time
        dt = str(datetime.now() - t0)
        inputfile="../tryout/"+tagname+".tif"
        object_key=bucketFolderOutput+"/"+tagname+"_"+dt+".tif"

        # Clean temporary files
        os.remove(yamlfile)
        os.remove(inputfile)

        # === Upload processed result back to S3 ===
        outputfile="../output/"+tagname+".tif"
        s3.upload_file(outputfile, BUCKET_NAME, object_key)
        # os.remove(outputfile)  # optionally delete after upload

        break  # stop after processing the first file
else:
    print("No file found in the specified bucket/prefix")

