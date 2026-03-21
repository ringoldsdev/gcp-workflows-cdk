"""Shared test fixtures and helpers."""

import sys
import os
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from cloud_workflows.models import parse_workflow


def parse(yaml_str: str):
    """Helper: dedent + parse a YAML string."""
    return parse_workflow(textwrap.dedent(yaml_str))
