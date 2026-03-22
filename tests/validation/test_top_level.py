"""Tests for top-level workflow structure (Form A and Form B)."""

import pytest
from pydantic import ValidationError

from cloud_workflows.models import parse_workflow, SimpleWorkflow, SubworkflowsWorkflow
from conftest import parse_fixture


def test_form_a_simple():
    """Form A: flat list of steps parses as SimpleWorkflow."""
    result = parse_fixture("top_level", "form_a_simple.yaml")
    assert isinstance(result, SimpleWorkflow)
    assert len(result.steps) == 2


def test_form_b_main():
    """Form B: dict with main block parses as SubworkflowsWorkflow."""
    result = parse_fixture("top_level", "form_b_main.yaml")
    assert isinstance(result, SubworkflowsWorkflow)
    assert "main" in result.workflows


def test_form_b_subworkflow():
    """Form B with main and subworkflow has both workflows."""
    result = parse_fixture("top_level", "form_b_subworkflow.yaml")
    assert isinstance(result, SubworkflowsWorkflow)
    assert "main" in result.workflows
    assert "greet" in result.workflows


def test_form_b_no_main():
    """Form B without 'main' key raises ValidationError."""
    with pytest.raises(ValidationError):
        parse_fixture("top_level", "form_b_no_main.yaml")


def test_params_defaults():
    """Subworkflow params with default values are parsed correctly."""
    result = parse_fixture("top_level", "params_defaults.yaml")
    assert isinstance(result, SubworkflowsWorkflow)
    my_sub = result.workflows["my_sub"]
    assert my_sub.params is not None
    assert len(my_sub.params) == 3


def test_invalid_not_list_or_dict():
    """Parsing a scalar YAML value raises ValueError."""
    with pytest.raises(ValueError):
        parse_workflow("42")


def test_empty_list():
    """Parsing an empty list produces a SimpleWorkflow with no steps."""
    result = parse_workflow("[]")
    assert isinstance(result, SimpleWorkflow)
    assert len(result.steps) == 0
