"""Tests for top-level workflow structure (Form A and Form B)."""

import textwrap

import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, SimpleWorkflow, SubworkflowsWorkflow


def test_form_a_simple():
    """Form A: flat list of steps parses as SimpleWorkflow."""
    yaml_str = textwrap.dedent("""\
        - assign_vars:
            assign:
              - message: "hello"
        - return_result:
            return: ${message}
    """)
    result = parse_workflow(yaml_str)
    assert isinstance(result, SimpleWorkflow)
    assert len(result.steps) == 2


def test_form_b_main():
    """Form B: dict with main block parses as SubworkflowsWorkflow."""
    yaml_str = textwrap.dedent("""\
        main:
            params: [args]
            steps:
                - step1:
                    return: ${args.name}
    """)
    result = parse_workflow(yaml_str)
    assert isinstance(result, SubworkflowsWorkflow)
    assert "main" in result.workflows


def test_form_b_subworkflow():
    """Form B with main and subworkflow has both workflows."""
    yaml_str = textwrap.dedent("""\
        main:
            params: [args]
            steps:
                - call_sub:
                    call: greet
                    args:
                        name: ${args.name}
                    result: greeting
                - done:
                    return: ${greeting}

        greet:
            params: [name]
            steps:
                - build:
                    return: ${"Hello, " + name}
    """)
    result = parse_workflow(yaml_str)
    assert isinstance(result, SubworkflowsWorkflow)
    assert "main" in result.workflows
    assert "greet" in result.workflows


def test_form_b_no_main():
    """Form B without 'main' key raises ValidationError."""
    yaml_str = textwrap.dedent("""\
        my_subworkflow:
            params: [x]
            steps:
                - step1:
                    return: ${x}
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)


def test_params_defaults():
    """Subworkflow params with default values are parsed correctly."""
    yaml_str = textwrap.dedent("""\
        main:
            steps:
                - call_sub:
                    call: my_sub
                    args:
                        first: "Alice"
                    result: r
                - done:
                    return: ${r}

        my_sub:
            params: [first, last: "Smith", country: "US"]
            steps:
                - build:
                    return: ${"Hello " + first + " " + last + " from " + country}
    """)
    result = parse_workflow(yaml_str)
    assert isinstance(result, SubworkflowsWorkflow)
    my_sub = result.workflows["my_sub"]
    assert my_sub.params is not None
    assert len(my_sub.params) == 3


def test_invalid_not_list_or_dict():
    """Parsing a scalar YAML value raises ValueError."""
    yaml_str = "42"
    with pytest.raises(ValueError):
        parse_workflow(yaml_str)


def test_empty_list():
    """Parsing an empty list produces a SimpleWorkflow with no steps."""
    yaml_str = "[]"
    result = parse_workflow(yaml_str)
    assert isinstance(result, SimpleWorkflow)
    assert len(result.steps) == 0
