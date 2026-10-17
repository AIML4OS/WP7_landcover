"""Helpers shared by the command line tools."""
import argparse
from typing import Optional

from landcover_pipeline.storage.path import execution_project_id


def add_run_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run",
        default=None,
        help="Execution name: works on <project>/execution/<run> "
             "(status, outputs, template and quality of that execution). "
             "For flairhub it is rgb or irg. Without it the project itself is used.",
    )


def resolve_project(project: str, run: Optional[str] = None) -> str:
    """Project id the stage must work on: the project or one of its executions."""
    return execution_project_id(project, run)
