# WP7_landcover
Land cover classification at regional level (NUTS2) using CoSIA deep learning model on high resolution aerial images.

Short description of the scripts and use:
+ **ECW2TIFF_RGBINF.py**: converts original ecw compressed files in GeoTiff format;
+ **RunProcess.py**: runs the model for inference
+ **IT_CONFIG.ini**: parameters needed for the previous scripts, you need to insert here the access key and the secret key; note: must be in the same folder of the scripts; 
+ **proto.yaml**: prototype to be modified by the RunProcess.py script
