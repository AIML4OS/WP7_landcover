# WP7_landcover
Land cover classification at regional level (NUTS2) using CoSIA deep learning model on high resolution aerial images.

Short description of the scripts and use:
+ IT Scripts
+ **ECW2TIFF_RGBINF.py**: converts original ecw compressed files in GeoTiff format;
+ **RunProcess.py**: runs the model for inference
+ **IT_CONFIG.ini**: parameters needed for the previous scripts, you need to insert here the access key and the secret key; note: must be in the same folder of the scripts; 
+ **proto.yaml**: prototype to be modified by the RunProcess.py script
+ **flair-detection.sh**: shell commands to run flair-detect from RunProcess.py ; do not edit

+ DK Scripts
+ **1_bash_run_flair.txt** run Flair
+ **run_flair.py**  This script runs the flair model using the correct settings file
+ **extract_output_info_matching_coord.py** This script gets the predicted classes from the flair model stored in .tif files for the pixel closest to each of the sampled coordinates 
 and stores these as well as additional metadata (pixel row/col, pixel number, pixel midpoint coordinates, sampled coordinates, band-value = class)
 make sure to change the output file as well as the location of the model output files.

