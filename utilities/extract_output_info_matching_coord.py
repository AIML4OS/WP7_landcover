# This script gets the predicted classes from the flair model stored in .tif files for the pixel closest to each of the sampled coordinates 
# and stores these as well as additional metadata (pixel row/col, pixel number, pixel midpoint coordinates, sampled coordinates, band-value = class)
# make sure to change the output file as well as the location of the model output files.
# Author: Jolien Cremers

import os
import rasterio
from rasterio.windows import Window
from rasterio.transform import xy
from tqdm import tqdm

# Function to load coordinates from tabular .txt file
def read_coordinates(file_path):
    coords = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                easting, northing = map(float, parts)
                coords.append((easting, northing))
    return coords

# Define input and output paths
coord_file = '/AIML4OS/WP7/analysis/data/random_points_nuts2vaerdi=DK01_fid=17_seed=4_coord.txt'
tif_folder = '/AIML4OS/WP7/model/output/small_irg/'
output_file = '/AIML4OS/WP7/analysis/data/small_irg_predictions_random_points_nuts2vaerdi=DK01_fid=17_seed=4_coord.txt'
log_path = output_file.replace('.txt', '_summary.log')

# Read coordinates
target_coords = read_coordinates(coord_file)

# Get list of .tif files
tif_files = [f for f in os.listdir(tif_folder) if f.endswith('.tif')]

# Write output including source filename
pixel_counter = 1
with open(output_file, 'w') as f_out:
    # Define and write output header
    f_out.write("pixel_id\tpixel_row_index\tpixel_col_index\tinput_easting\tinput_northing\tpixel_easting\tpixel_northing\tband_1\tsource_file\n")

    skipped_coords = {}  # filename → number of skipped coordinates for log file

    for filename in tqdm(tif_files, desc="Processing .tif files"):
        filepath = os.path.join(tif_folder, filename)

        try:
            with rasterio.open(filepath) as src:
                band_array = src.read(1)

                pixel_indices = []
                for easting, northing in target_coords:
                    try:
                        # Check if target_coord is out of bounds for .tif file to prevent wrong matches in src.index()
                        if not (src.bounds.left <= easting <= src.bounds.right and
                                src.bounds.bottom <= northing <= src.bounds.top):
                           skipped_coords[filename] = skipped_coords.get(filename, 0) + 1
                           continue
                        # Match easting and northing of target_coord to pixel indices (row and column) and append
                        row, col = src.index(easting, northing)
                        pixel_indices.append((row, col, easting, northing))
                    except Exception:
                        continue

                for row, col, easting, northing in pixel_indices:
                    try:
                        # Get band value (classification) from pixel index
                        value = band_array[row, col]
                        # Save pixel id
                        pixel_id = f"Pixel_{pixel_counter}"

                        # Extract pixel center coordinates from raster
                        pixel_x, pixel_y = xy(src.transform, row, col)

                        #Write output to file
                        f_out.write(
                            f"{pixel_id}\t{row}\t{col}\t{easting}\t{northing}\t"
                            f"{pixel_x}\t{pixel_y}\t{value}\t{filename}\n"
                        )
                        pixel_counter += 1
                    except Exception:
                        continue
        except Exception as file_err:
            print(f"Skipping file {filename}: {file_err}")



# Write summary of skipped coordinates to log file
with open(log_path, 'w') as log:
    log.write("Summary of skipped coordinates due to out-of-bounds:\n\n")
    total_skips = sum(skipped_coords.values())
    for fname, count in skipped_coords.items():
        log.write(f"{fname}: {count} coordinates skipped\n")
    log.write(f"\nTotal skipped: {total_skips} coordinates across {len(skipped_coords)} files.\n")

# Print only final tally to console
print(f"\nTotal skipped: {total_skips} coordinates across {len(skipped_coords)} files.\n")