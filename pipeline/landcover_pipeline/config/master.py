import yaml
from pathlib import Path

REQUIRED_PROJECT_KEYS = ["country", "region", "year"]

def load_master_config(path: str) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Master config not found: {path}")

    with path.open() as f:
        cfg = yaml.safe_load(f)

    return cfg


def validate_master_config(cfg: dict) -> None:
    if "project" not in cfg:
        raise ValueError("Missing 'project' section in master config")

    project = cfg["project"]
    for key in REQUIRED_PROJECT_KEYS:
        if key not in project:
            raise ValueError(f"Missing project.{key} in master config")
    return "project validate OK"


def build_project_id(cfg: dict) -> str:
    p = cfg["project"]
    return f"{p['country']}/{p['region']}/{p['year']}"


