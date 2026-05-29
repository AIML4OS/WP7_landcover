"""
Utility Functions for Raster Data Extraction

This module provides utility functions for extracting pixel values from raster files
at specified coordinates and handling coordinate data.

Functions:
    - process_tif_file: Extract band values from .tif raster at coordinates
    - read_coordinates: Load coordinates from tab-delimited text file
    - convert_column_to_string: Convert DataFrame column to string type

"""
import os
import pandas as pd
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import xy

def process_tif_file(filename, tif_folder, target_coords, additional_cols):
    """
    Extract band values from a .tif raster file at specified coordinates.
    
    This function processes a single raster file to extract pixel values (band data)
    at locations corresponding to input coordinates. It performs spatial matching,
    coordinate-to-pixel conversion, and extracts all 19 bands for valid pixels.
    
    Process:
        1. Opens the .tif raster file
        2. Filters coordinates to those within raster bounds
        3. Converts geographic coordinates to pixel row/col indices
        4. Validates pixel indices are within raster dimensions
        5. Reads all 19 band values for each valid pixel
        6. Retrieves pixel center coordinates
        7. Formats output with metadata and band values
    
    Args:
        filename (str): Name of the .tif file to process (without path)
        tif_folder (str): Directory path containing the .tif file
        target_coords (list): List of coordinate tuples with format:
            (point_id, easting, northing, *additional_values)
            where additional_values are optional metadata columns
        additional_cols (list): Names of additional metadata columns 
            (used for output formatting, not processing)
    
    Returns:
        tuple: (results, filename, skipped_count) containing:
            - results (list): List of formatted output strings, one per valid coordinate.
                Each string contains: point_id, pixel_row, pixel_col, input_easting,
                input_northing, pixel_easting, pixel_northing, additional_metadata,
                19 band values, source_filename (tab-separated)
            - filename (str): Original filename that was processed
            - skipped_count (int): Number of coordinates skipped due to being 
                outside raster bounds or having invalid pixel indices
    
    Notes:
        - Coordinates outside the raster bounds are skipped
        - Invalid pixel indices (negative or beyond raster dimensions) are skipped
        - Errors during processing of individual coordinates are silently caught
        - The function expects exactly 19 bands in the raster
        - Uses rasterio's Window for efficient single-pixel reading
    
    Example output format:
        "POINT_001\\t245\\t1023\\t725000.5\\t6175000.2\\t725000.0\\t6175000.0\\tSTRATA_A\\t18\\t0.95\\t0.02\\t...\\tfile.tif\\n"
    """
    # Initialize counters for tracking processing statistics
    skipped_count = 0  # Coordinates outside bounds or with invalid indices
    bounds_count = 0   # Coordinates within raster bounds (for debugging)
    index_count = 0    # Valid pixel indices within raster (for debugging)
    read_count = 0     # Successfully read pixels (for debugging)
    
    try:
        # Construct full file path.
        # For GDAL VSI paths ("/vsis3/...") keep POSIX separators.
        # On Windows, os.path.join would inject "\" and break URL parsing.
        if str(filename).startswith("/vsis3/"):
            filepath = str(filename)
        elif str(tif_folder).startswith("/vsis3/"):
            filepath = f"{str(tif_folder).rstrip('/')}/{str(filename).lstrip('/')}"
        else:
            filepath = os.path.join(tif_folder, filename)
        
        # Open raster file and process coordinates
        with rasterio.open(filepath) as src:
            # Get affine transformation matrix for coordinate conversions
            transform = src.transform
            pixel_indices = []
            
            # ================================================================
            # First Pass: Validate coordinates and convert to pixel indices
            # ================================================================
            for coord in target_coords:
                try:
                    # Unpack coordinate tuple
                    point_id = coord[0]              # Unique point identifier
                    easting = coord[1]               # X coordinate (ETRS89)
                    northing = coord[2]              # Y coordinate (ETRS89)
                    # Extract any additional metadata values
                    additional_values = tuple(coord[3:]) if len(coord) > 3 else ()
                    
                    # Check if coordinate falls within raster spatial extent
                    # Skip coordinates outside the raster bounds
                    if not (src.bounds.left <= easting <= src.bounds.right and
                            src.bounds.bottom <= northing <= src.bounds.top):
                        skipped_count += 1
                        continue
                    bounds_count += 1
                    
                    # Convert geographic coordinates to raster pixel row/col indices
                    # src.index() returns (row, col) for the pixel containing the coordinate
                    row, col = src.index(easting, northing)
                    
                    # Validate that pixel indices are within raster array dimensions
                    # Negative indices or indices beyond array size are invalid
                    if row < 0 or row >= src.height or col < 0 or col >= src.width:
                        skipped_count += 1
                        continue
                    
                    index_count += 1
                    # Store validated pixel information for second pass
                    pixel_indices.append((point_id, row, col, easting, northing) + additional_values)
                except Exception as e:
                    # Skip individual coordinates that cause errors
                    continue

            # ================================================================
            # Second Pass: Extract band values for valid pixels
            # ================================================================
            results = []
            for pixel_data in pixel_indices:
                try:
                    # Unpack stored pixel information from first pass
                    point_id = pixel_data[0]
                    row = pixel_data[1]
                    col = pixel_data[2]
                    easting = pixel_data[3]          # Original input coordinate
                    northing = pixel_data[4]         # Original input coordinate
                    additional_values = pixel_data[5:] if len(pixel_data) > 5 else ()

                    # Create a 1x1 pixel window at the target pixel location
                    # Window specifies: starting column, starting row, width=1, height=1
                    window = Window(col_off=col, row_off=row, width=1, height=1)
                    
                    # Read all 19 bands for this single pixel using the window
                    # Bands are numbered 1-19 (rasterio uses 1-based indexing)
                    # flatten() converts the 3D array (bands, height, width) to 1D
                    band_values = src.read(list(range(1, 20)), window=window).flatten()
                    read_count += 1
                    
                    # Convert band values array to tab-separated string
                    band_values_str = "\t".join(map(str, band_values))
                    
                    # Get the geographic coordinates of the pixel center
                    # xy() converts pixel row/col back to geographic coordinates
                    # using the affine transformation matrix
                    pixel_x, pixel_y = xy(transform, row, col)
                    
                    # Format additional metadata values as tab-separated string
                    additional_values_str = "\t".join(map(str, additional_values)) if additional_values else ""
                    
                    # Construct output line with all information
                    # Format: point_id, row, col, input_easting, input_northing,
                    #         pixel_center_x, pixel_center_y, [additional_metadata],
                    #         band_1, band_2, ..., band_19, source_filename
                    if additional_values_str:
                        results.append(
                            f"{point_id}\t{row}\t{col}\t{easting}\t{northing}\t{pixel_x}\t{pixel_y}\t{additional_values_str}\t{band_values_str}\t{filename}\n"
                        )
                    else:
                        # If no additional metadata, omit that field
                        results.append(
                            f"{point_id}\t{row}\t{col}\t{easting}\t{northing}\t{pixel_x}\t{pixel_y}\t{band_values_str}\t{filename}\n"
                        )
                except Exception as e:
                    # Skip individual pixels that cause errors during extraction
                    continue
            return (results, filename, skipped_count)
    except Exception as file_err:
        print(f"Skipping file {filename}: {file_err}")
        return ([], filename, 0)


def read_coordinates(file_path, easting_col, northing_col, point_id_col, additional_cols):
    """
    Load coordinates and metadata from a tab-delimited text file.
    
    This function reads coordinate data from a tab-separated file and validates
    that all required columns are present. It returns coordinates as a list of
    tuples, with each tuple containing point ID, easting, northing, and any
    additional metadata values.
    
    Process:
        1. Read tab-delimited file into pandas DataFrame
        2. Validate that all required columns exist
        3. Extract specified columns in order: point_id, easting, northing, additional_cols
        4. Convert DataFrame to list of tuples
    
    Args:
        file_path (str): Path to the input tab-delimited text file
        easting_col (str): Name of the column containing easting coordinates (X)
        northing_col (str): Name of the column containing northing coordinates (Y)
        point_id_col (str): Name of the column containing unique point identifiers
        additional_cols (list): List of additional column names to extract
            (e.g., ["STRATUM_LUCAS", "STR18"] or ["SURVEY_LC1", "SURVEY_LC2"])
    
    Returns:
        list: List of tuples, where each tuple contains:
            (point_id, easting, northing, *additional_values)
            Example: [('POINT_001', 725000.5, 6175000.2, 'STRATA_A', 18),
                     ('POINT_002', 725100.3, 6175050.1, 'STRATA_B', 12), ...]
    
    Raises:
        ValueError: If the file cannot be read or parsed
        KeyError: If any required column is missing from the input file
    
    Notes:
        - Input file must be tab-delimited
        - File must contain headers in the first row
        - Point ID is always returned as the first element in each tuple
        - Order of elements: point_id, easting, northing, then additional columns
          in the order specified in additional_cols
    
    Example:
        >>> coords = read_coordinates(
        ...     '/path/to/coords.txt',
        ...     'EASTING_ETRS89',
        ...     'NORTHING_ETRS89',
        ...     'POINT_ID',
        ...     ['STRATUM_LUCAS', 'STR18']
        ... )
        >>> print(coords[0])
        ('DK01_001', 725000.5, 6175000.2, 'A', 18)
    """
    try:
        # Read tab-delimited file into DataFrame
        df = pd.read_csv(file_path, delimiter="\t")
        
        # Build list of all required columns
        required_columns = [easting_col, northing_col, point_id_col] + additional_cols
        
        # Validate that all required columns exist in the file
        for col in required_columns:
            if col not in df.columns:
                raise KeyError(f"Required column '{col}' is missing in the input file.")
        
        # Extract columns in specific order: point_id first, then easting, northing, additional
        # Convert DataFrame to list of lists, then each list becomes a tuple
        coords = df[[point_id_col, easting_col, northing_col] + additional_cols].values.tolist()
        return coords
    except Exception as e:
        raise ValueError(f"Error reading coordinates from file: {e}")

def convert_column_to_string(df, col_name, col_description="column"):
    """
    Convert a column to string, handling both numeric and string data types.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe containing the column
    col_name : str
        The name of the column to convert
    col_description : str
        Description of the column for logging purposes
        
    Returns:
    --------
    pandas.DataFrame
        The dataframe with the converted column
    """
    print(f"\n{col_description} '{col_name}' info:")
    print(f"  Original data type: {df[col_name].dtype}")
    print(f"  Sample values: {df[col_name].head(10).tolist()}")
    
    # Try to convert to numeric - if successful, the data is numeric
    numeric_conversion = pd.to_numeric(df[col_name], errors='coerce')
    is_numeric = not numeric_conversion.isna().all()
    
    if is_numeric:
        # Original values are numeric/integer type - convert directly to int then string
        df[col_name] = numeric_conversion.fillna(0).astype(int).astype(str)
        print(f"  Converted numeric to string")
    else:
        # Original values are string/text type - keep as string
        df[col_name] = df[col_name].astype(str)
        print(f"  Kept as string type")
    
    print(f"  Final string values: {df[col_name].head(10).tolist()}")
    
    # Check if '<NA>' appears
    if '<NA>' in df[col_name].values:
        print(f"  WARNING: '<NA>' found in data - this indicates conversion issues")
    
    return df
