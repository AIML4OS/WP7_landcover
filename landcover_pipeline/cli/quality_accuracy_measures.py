import argparse
import importlib.util
from pathlib import Path


def _load_accuracy_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "Pipeline code for accuracy assessment"
        / "accuracy_measures.py"
    )
    spec = importlib.util.spec_from_file_location("quality_accuracy_module", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run legacy accuracy measures from predictions file."
    )
    parser.add_argument(
        "--predictions-file",
        required=True,
        help="Input predictions txt (e.g. predictions_IT_veneto_2021_crop2176.txt).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    module = _load_accuracy_module()
    output_file = module.run_accuracy_measures(args.predictions_file)
    print(f"Accuracy report: {output_file}")


if __name__ == "__main__":
    main()

