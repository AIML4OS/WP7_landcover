import argparse
import importlib.util
from pathlib import Path


def _load_converter_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Pipeline code for accuracy assessment"
        / "convert_WGS84_to_ETRS89.py"
    )
    spec = importlib.util.spec_from_file_location("quality_convert_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert WGS84 coordinates to projected CRS for quality assessment."
    )
    parser.add_argument("--epsg", required=True, help="Target CRS, e.g. EPSG:32632")
    parser.add_argument("--nuts2", required=True, help="NUTS2 code filter, e.g. ITH3")
    parser.add_argument("--input-file", required=True, help="Input CSV/XLSX file path")
    parser.add_argument(
        "--modality",
        default="LUCAS",
        choices=["LUCAS", "MASTER"],
        help="Input schema modality (default: LUCAS)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    module = _load_converter_module()
    output_txt = module.convert_wgs84_to_etrs89(
        EPSG=args.epsg,
        NUTS2=args.nuts2,
        INPUT_FILE=args.input_file,
        modality=args.modality,
    )
    print(f"Output file: {output_txt}")


if __name__ == "__main__":
    main()

