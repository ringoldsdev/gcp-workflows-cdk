"""Tests for nested steps validation."""

import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow


def test_nested_steps():
    """VALID: nested steps blocks with variable references."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - group_a:
            steps:
              - step1:
                  assign:
                    - x: 1
              - step2:
                  assign:
                    - y: ${x + 1}
        - group_b:
            steps:
              - step3:
                  return: ${y}
    """)
    )
    assert len(wf.steps) == 2
    group_a = wf.steps[0].body
    assert len(group_a.steps) == 2
    assert group_a.steps[0].name == "step1"
    assert group_a.steps[1].name == "step2"
    group_b = wf.steps[1].body
    assert len(group_b.steps) == 1
    assert group_b.steps[0].name == "step3"


def test_nested_steps_with_next():
    """VALID: nested steps with a next field to skip ahead."""
    wf = parse_workflow(
        textwrap.dedent("""\
        - group:
            steps:
              - init:
                  assign:
                    - x: 42
            next: done
        - skipped:
            assign:
              - x: 0
        - done:
            return: ${x}
    """)
    )
    assert len(wf.steps) == 3
    body = wf.steps[0].body
    assert len(body.steps) == 1
    assert body.next == "done"
