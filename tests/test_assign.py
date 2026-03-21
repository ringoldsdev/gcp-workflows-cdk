"""Tests for assign step validation."""

import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, SimpleWorkflow, AssignStep
from conftest import parse_fixture, load_fixture


def test_assign_basic():
    """VALID: basic assign with multiple types."""
    wf = parse_fixture("assign", "basic.yaml")
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert len(body.assign) == 6


def test_assign_expressions():
    """VALID: assign with expression references."""
    wf = parse_fixture("assign", "expressions.yaml")
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert len(body.assign) == 4


def test_assign_with_next():
    """VALID: assign step with next field."""
    wf = parse_fixture("assign", "with_next.yaml")
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert body.next == "done"


def test_assign_over_50():
    """INVALID: more than 50 assignments per step."""
    with pytest.raises(ValidationError):
        parse_fixture("assign", "over_50.yaml")


def test_assign_empty():
    """INVALID: empty assign list."""
    with pytest.raises(ValidationError):
        parse_fixture("assign", "empty.yaml")


def test_assign_multi_key_dict():
    """INVALID: assignment dict with more than one key."""
    with pytest.raises(ValidationError):
        parse_fixture("assign", "multi_key_dict.yaml")
