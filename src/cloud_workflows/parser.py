"""Parser module: convenience functions for YAML validation."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from .models import Workflow, parse_workflow


def validate_yaml(yaml_str: str) -> Workflow:
    """Parse and validate a Cloud Workflows YAML string."""
    return parse_workflow(yaml_str)


def validate_file(path: Union[str, Path]) -> Workflow:
    """Parse and validate a Cloud Workflows YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return parse_workflow(f.read())
