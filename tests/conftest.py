"""Shared test fixtures and helpers."""

import sys
import os
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from cloud_workflows.models import parse_workflow

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def parse(yaml_str: str):
    """Helper: dedent + parse a YAML string."""
    return parse_workflow(textwrap.dedent(yaml_str))


def load_fixture(*path_parts: str) -> str:
    """Load a YAML fixture file and return its contents as a string.

    Usage:
        load_fixture("assign", "basic.yaml")
        load_fixture("call", "http_get.yaml")
    """
    fixture_path = FIXTURES_DIR.joinpath(*path_parts)
    return fixture_path.read_text(encoding="utf-8")


def parse_fixture(*path_parts: str):
    """Load a YAML fixture file and parse it into a workflow.

    Usage:
        parse_fixture("assign", "basic.yaml")
    """
    return parse_workflow(load_fixture(*path_parts))
