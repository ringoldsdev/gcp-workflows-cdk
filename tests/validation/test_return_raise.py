"""Tests for return and raise step validation."""

import pytest
from pydantic import ValidationError

from cloud_workflows.models import parse_workflow
from conftest import parse_fixture


def test_return_scalar():
    """VALID: return with a scalar value."""
    wf = parse_fixture("return_raise", "return_scalar.yaml")
    body = wf.steps[0].body
    assert body.return_value == 42


def test_return_map():
    """VALID: return with a map value."""
    wf = parse_fixture("return_raise", "return_map.yaml")
    body = wf.steps[0].body
    assert isinstance(body.return_value, dict)


def test_return_expression():
    """VALID: return with an expression referencing a variable."""
    wf = parse_fixture("return_raise", "return_expression.yaml")
    assert len(wf.steps) == 2
    body = wf.steps[1].body
    assert body.return_value == "${x * 2}"


def test_raise_string():
    """VALID: raise with a string message."""
    wf = parse_fixture("return_raise", "raise_string.yaml")
    body = wf.steps[0].body
    assert body.raise_value == "Something went wrong"


def test_raise_map():
    """VALID: raise with a map containing code and message."""
    wf = parse_fixture("return_raise", "raise_map.yaml")
    body = wf.steps[0].body
    assert isinstance(body.raise_value, dict)
