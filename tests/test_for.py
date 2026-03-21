import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, ForStep, ForBody
from conftest import parse_fixture


def test_for_list():
    """Valid: iterate over a list with 'in'."""
    wf = parse_fixture("for", "list.yaml")
    step = wf.steps[1]
    body = step.body
    assert isinstance(body, ForStep)
    for_body = body.for_
    assert for_body.value == "item"
    assert for_body.in_ == "${items}"
    assert for_body.range is None
    assert for_body.index is None
    assert len(for_body.steps) == 1


def test_for_range():
    """Valid: iterate over a range."""
    wf = parse_fixture("for", "range.yaml")
    step = wf.steps[1]
    body = step.body
    assert isinstance(body, ForStep)
    for_body = body.for_
    assert for_body.value == "i"
    assert for_body.range == [1, 10]
    assert for_body.in_ is None
    assert for_body.index is None
    assert len(for_body.steps) == 1


def test_for_index():
    """Valid: iterate with an index variable."""
    wf = parse_fixture("for", "index.yaml")
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, ForStep)
    for_body = body.for_
    assert for_body.value == "item"
    assert for_body.index == "idx"
    assert for_body.in_ == ["a", "b", "c"]
    assert for_body.range is None


def test_for_both_in_range():
    """Invalid: 'in' and 'range' are mutually exclusive."""
    with pytest.raises(ValidationError):
        parse_fixture("for", "both_in_range.yaml")


def test_for_neither():
    """Invalid: must have one of 'in' or 'range'."""
    with pytest.raises(ValidationError):
        parse_fixture("for", "neither.yaml")


def test_for_index_with_range():
    """Invalid: 'index' is only valid with 'in', not 'range'."""
    with pytest.raises(ValidationError):
        parse_fixture("for", "index_with_range.yaml")


def test_for_break_continue():
    """Valid: for loop with break and continue via switch/next."""
    wf = parse_fixture("for", "break_continue.yaml")
    step = wf.steps[1]
    body = step.body
    assert isinstance(body, ForStep)
    for_body = body.for_
    assert for_body.value == "item"
    assert for_body.in_ == [1, None, 3, "STOP", 5]
    assert len(for_body.steps) == 2
