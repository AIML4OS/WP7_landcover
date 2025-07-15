
import os
from osgeo import gdal

print("Starting conversion...")

# === CONFIGURATION ===
input_folder = r"C:\Users\UTENTE\Desktop\DESKTOP\AreeVerdi\RGB-CT_1\RGB"
output_folder = input_folder  # You can change this if you want to save the output elsewhere

# Print input folder and its contents
print(f"Input folder: {input_folder}")
print("Files found:", os.listdir(input_folder))

# Loop through all .ecw files in the folder
for filename in os.listdir(input_folder):
    print(f"Processing file: {filename}")
    
    if filename.lower().endswith(".ecw"):
        ecw_path = os.path.join(input_folder, filename)
        output_filename = os.path.splitext(filename)[0] + ".tif"
        tif_path = os.path.join(output_folder, output_filename)

        print(f"Converting: {ecw_path} -> {tif_path}")

        gdal.Translate(
            tif_path,
            ecw_path,
            format="GTiff",
            creationOptions=[
                "COMPRESS=LZW",        # lossless compression
                "TILED=YES",           # enables tiling for better performance and overviews
                "BIGTIFF=IF_SAFER"     # allows large files if needed
            ]
        )

print("All conversions completed.")



