"""Tests for assign step validation."""

import textwrap

import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, SimpleWorkflow, AssignStep


def test_assign_basic():
    """VALID: basic assign with multiple types."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - init:
            assign:
              - x: 5
              - y: "hello"
              - z: true
              - w: null
              - list: [1, 2, 3]
              - map:
                  key1: "value1"
                  key2: "value2"
    """)
    )
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert len(body.assign) == 6


def test_assign_expressions():
    """VALID: assign with expression references."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - calc:
            assign:
              - x: 5
              - y: ${x + 1}
              - z: ${x * y}
              - msg: '${"Result: " + string(z)}'
    """)
    )
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert len(body.assign) == 4


def test_assign_with_next():
    """VALID: assign step with next field."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - init:
            assign:
              - x: 1
            next: done
        - skipped:
            assign:
              - x: 2
        - done:
            return: ${x}
    """)
    )
    assert isinstance(wf, SimpleWorkflow)
    body = wf.steps[0].body
    assert isinstance(body, AssignStep)
    assert body.next == "done"


def test_assign_over_50():
    """INVALID: more than 50 assignments per step."""
    assignments = "\n".join(f"      - v{i}: {i}" for i in range(1, 52))
    yaml_str = f"- too_many:\n    assign:\n{assignments}"
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)


def test_assign_empty():
    """INVALID: empty assign list."""
    with pytest.raises(ValidationError):
        parse_workflow(
            textwrap.dedent("""\
            - empty:
                assign: []
        """)
        )


def test_assign_multi_key_dict():
    """INVALID: assignment dict with more than one key."""
    with pytest.raises(ValidationError):
        parse_workflow(
            textwrap.dedent("""\
            - bad:
                assign:
                  - x: 1
                    y: 2
        """)
        )
