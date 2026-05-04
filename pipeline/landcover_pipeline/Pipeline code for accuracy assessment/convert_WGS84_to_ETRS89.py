"""
Convert WGS84 coordinates to a projected CRS and export a tab-separated file.

Main entrypoint:
    convert_wgs84_to_etrs89(EPSG, NUTS2, INPUT_FILE, modality="LUCAS")
"""

from pathlib import Path

import pandas as pd
from pyproj import Transformer


def _config_for_modality(modality: str) -> dict:
    mode = modality.strip().upper()
    if mode == "LUCAS":
        return {
            "longitude_col": "POINT_LONG",
            "latitude_col": "POINT_LAT",
            "nuts2_col": "POINT_NUTS2",
            "id_col": "POINT_ID",
            "output_columns": ["POINT_NUTS0", "POINT_NUTS3", "SURVEY_LC1", "SURVEY_LC2"],
            "csv_header": 0,
            "csv_separator": ",",
            "input_sheet_name": None,
        }
    if mode == "MASTER":
        return {
            "longitude_col": "X_WGS84",
            "latitude_col": "Y_WGS84",
            "nuts2_col": "NUTS2_21",
            "id_col": "POINT_ID",
            "output_columns": ["NUTS0_21", "NUTS3_21", "STRATUM_LUCAS", "STR18"],
            "csv_header": 0,
            "csv_separator": ",",
            "input_sheet_name": "Master_web",
        }
    raise ValueError(f"Unsupported modality '{modality}'. Use 'LUCAS' or 'MASTER'.")


def convert_wgs84_to_etrs89(EPSG: str, NUTS2: str, INPUT_FILE: str, modality: str = "LUCAS") -> str:
    """
    Convert WGS84 lon/lat to target projection and save a tab-separated output.

    Parameters
    ----------
    EPSG : str
        Target EPSG code (example: "EPSG:32632").
    NUTS2 : str
        NUTS2 code filter.
    INPUT_FILE : str
        Input .csv or .xlsx file path.
    modality : str
        Input schema profile, default "LUCAS". Supported: "LUCAS", "MASTER".

    Returns
    -------
    str
        Output txt path.
    """
    cfg = _config_for_modality(modality)
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    output_txt = input_path.with_name(
        f"{input_path.stem}_{NUTS2}_{EPSG.replace(':', '')}.txt"
    )

    mandatory_output_columns = [
        cfg["id_col"],
        cfg["nuts2_col"],
        cfg["longitude_col"],
        cfg["latitude_col"],
        "EASTING_ETRS89",
        "NORTHING_ETRS89",
    ]

    required_input_columns = list(
        set(mandatory_output_columns + cfg["output_columns"])
        - {"EASTING_ETRS89", "NORTHING_ETRS89", "PROJECTION_ETRS89"}
    )

    if input_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(
            input_path,
            sheet_name=cfg["input_sheet_name"],
            usecols=required_input_columns,
        )
    elif input_path.suffix.lower() == ".csv":
        df = pd.read_csv(
            input_path,
            header=cfg["csv_header"],
            delimiter=cfg["csv_separator"],
            usecols=required_input_columns,
        )
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .xlsx file.")

    required_columns = [cfg["id_col"], cfg["nuts2_col"], cfg["longitude_col"], cfg["latitude_col"]]
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise KeyError(f"Missing required columns in input file: {missing}")

    df[cfg["nuts2_col"]] = df[cfg["nuts2_col"]].astype(str).str.strip()
    df = df[df[cfg["nuts2_col"]] == str(NUTS2).strip()].copy()

    transformer = Transformer.from_crs("EPSG:4326", EPSG, always_xy=True)
    if not df.empty:
        easting, northing = transformer.transform(
            df[cfg["longitude_col"]].values, df[cfg["latitude_col"]].values
        )
        df["EASTING_ETRS89"] = easting
        df["NORTHING_ETRS89"] = northing
        df["PROJECTION_ETRS89"] = EPSG
    else:
        df["EASTING_ETRS89"] = None
        df["NORTHING_ETRS89"] = None
        df["PROJECTION_ETRS89"] = None

    all_output_columns = mandatory_output_columns + [
        c for c in cfg["output_columns"] if c not in mandatory_output_columns
    ]
    missing_out = set(all_output_columns) - set(df.columns)
    if missing_out:
        raise KeyError(f"Missing columns in output: {missing_out}")

    df = df[all_output_columns]
    df.to_csv(output_txt, sep="\t", index=False)
    print(f"Conversion complete. Saved to {output_txt}")
    return str(output_txt)

