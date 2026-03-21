import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, ForStep, ForBody


def test_for_list():
    """Valid: iterate over a list with 'in'."""
    yaml_text = textwrap.dedent("""\
        - init:
            assign:
              - total: 0
              - items: [1, 2, 3, 4, 5]
        - loop:
            for:
              value: item
              in: ${items}
              steps:
                - add:
                    assign:
                      - total: ${total + item}
        - done:
            return: ${total}
    """)
    wf = parse_workflow(yaml_text)
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
    yaml_text = textwrap.dedent("""\
        - init:
            assign:
              - total: 0
        - loop:
            for:
              value: i
              range: [1, 10]
              steps:
                - add:
                    assign:
                      - total: ${total + i}
        - done:
            return: ${total}
    """)
    wf = parse_workflow(yaml_text)
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
    yaml_text = textwrap.dedent("""\
        - loop:
            for:
              value: item
              index: idx
              in: ["a", "b", "c"]
              steps:
                - log:
                    call: sys.log
                    args:
                      text: '${"Item " + string(idx) + ": " + item}'
    """)
    wf = parse_workflow(yaml_text)
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
    yaml_text = textwrap.dedent("""\
        - loop:
            for:
              value: x
              in: [1, 2, 3]
              range: [1, 10]
              steps:
                - noop:
                    assign:
                      - y: ${x}
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_text)


def test_for_neither():
    """Invalid: must have one of 'in' or 'range'."""
    yaml_text = textwrap.dedent("""\
        - loop:
            for:
              value: x
              steps:
                - noop:
                    assign:
                      - y: ${x}
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_text)


def test_for_index_with_range():
    """Invalid: 'index' is only valid with 'in', not 'range'."""
    yaml_text = textwrap.dedent("""\
        - loop:
            for:
              value: i
              index: idx
              range: [1, 10]
              steps:
                - noop:
                    assign:
                      - x: ${i}
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_text)


def test_for_break_continue():
    """Valid: for loop with break and continue via switch/next."""
    yaml_text = textwrap.dedent("""\
        - init:
            assign:
              - results: []
        - loop:
            for:
              value: item
              in: [1, null, 3, "STOP", 5]
              steps:
                - skip_null:
                    switch:
                      - condition: ${item == null}
                        next: continue
                      - condition: ${item == "STOP"}
                        next: break
                - collect:
                    assign:
                      - results: ${list.concat(results, [item])}
        - done:
            return: ${results}
    """)
    wf = parse_workflow(yaml_text)
    step = wf.steps[1]
    body = step.body
    assert isinstance(body, ForStep)
    for_body = body.for_
    assert for_body.value == "item"
    assert for_body.in_ == [1, None, 3, "STOP", 5]
    assert len(for_body.steps) == 2
