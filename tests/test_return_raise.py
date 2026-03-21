"""Tests for return and raise step validation."""

import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow


def test_return_scalar():
    """VALID: return with a scalar value."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - done:
            return: 42
    """)
    )
    body = wf.steps[0].body
    assert body.return_ == 42


def test_return_map():
    """VALID: return with a map value."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - done:
            return:
              status: "ok"
              count: 5
    """)
    )
    body = wf.steps[0].body
    assert isinstance(body.return_, dict)


def test_return_expression():
    """VALID: return with an expression referencing a variable."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - init:
            assign:
              - x: 10
        - done:
            return: ${x * 2}
    """)
    )
    assert len(wf.steps) == 2
    body = wf.steps[1].body
    assert body.return_ == "${x * 2}"


def test_raise_string():
    """VALID: raise with a string message."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - fail:
            raise: "Something went wrong"
    """)
    )
    body = wf.steps[0].body
    assert body.raise_ == "Something went wrong"


def test_raise_map():
    """VALID: raise with a map containing code and message."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - fail:
            raise:
              code: 404
              message: "Resource not found"
    """)
    )
    body = wf.steps[0].body
    assert isinstance(body.raise_, dict)
