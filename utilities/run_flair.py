# This script runs the flair model using the correct settings file (make sure to check/change the paths and the config file location and update the contents of the .config file if needed)
# Author: Jolien Cremers

import subprocess
import re

CONFIG_FILE = "/AIML4OS/WP7/model/config/config_detect_small_irg.yaml"
PATHS_FILE = "/AIML4OS/WP7/model/config/flair_swin-small-irg_settings.txt"

def update_config_line(file_path, key, value):
    with open(file_path, "r") as f:
        lines = f.readlines()
    pattern = re.compile(rf"^{key}:\s.*")
    with open(file_path, "w") as f:
        for line in lines:
            if pattern.match(line):
                f.write(f"{key}: {value}\n")
            else:
                f.write(line)

print("  Running flair-detect with:")
print(f"   Config: {CONFIG_FILE}")
print(f"   Path list: {PATHS_FILE}")
print("-----------------------------------------")

with open(PATHS_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        # Parse line using comma or space as delimiter
        tokens = re.split(r"[,\s]+", line)
        if len(tokens) < 5:
            print(f"Skipping invalid line: {line}")
            continue

        OUTPUT_PATH, OUTPUT_NAME, INPUT_PATH, PIXELS, MARGIN = tokens

        if not INPUT_PATH or not OUTPUT_PATH:
            print(f"Skipping invalid line: {line}")
            continue

        update_config_line(CONFIG_FILE, "input_img_path", INPUT_PATH)
        update_config_line(CONFIG_FILE, "output_path", OUTPUT_PATH)
        update_config_line(CONFIG_FILE, "output_name", OUTPUT_NAME)
        update_config_line(CONFIG_FILE, "img_pixels_detection", PIXELS)
        update_config_line(CONFIG_FILE, "margin", MARGIN)

        print("   Updated config with:")
        print(f"   input_img_path: {INPUT_PATH}")
        print(f"   output_path: {OUTPUT_PATH}")
        print(f"   output_name: {OUTPUT_NAME}")
        print(f"   img_pixels_detection: {PIXELS}")
        print(f"   margin: {MARGIN}")

        print(f'Running: flair-detect --conf="{CONFIG_FILE}"')
        subprocess.run(["flair-detect", "--conf", CONFIG_FILE], check=True)

        print(" Done this model")
        print("-----------------------------")

print("All models estimated")