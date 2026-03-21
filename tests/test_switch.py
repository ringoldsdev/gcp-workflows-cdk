import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, SwitchStep


def test_switch_basic():
    yaml_str = textwrap.dedent("""\
        - init:
            assign:
              - x: 5
        - check:
            switch:
              - condition: ${x < 10}
                next: small
              - condition: ${x >= 10}
                next: big
        - small:
            return: "small"
        - big:
            return: "big"
    """)
    wf = parse_workflow(yaml_str)
    switch_step = wf.steps[1]
    assert isinstance(switch_step.body, SwitchStep)
    assert len(switch_step.body.switch) == 2


def test_switch_fallthrough():
    yaml_str = textwrap.dedent("""\
        - check:
            switch:
              - condition: ${x < 0}
                return: "negative"
            next: positive
        - positive:
            return: "non-negative"
    """)
    wf = parse_workflow(yaml_str)
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)
    assert switch_step.body.next == "positive"


def test_switch_embedded_steps():
    yaml_str = textwrap.dedent("""\
        - check:
            switch:
              - condition: ${x == 1}
                steps:
                  - compute:
                      assign:
                        - result: ${x + 10}
                  - done:
                      return: ${result}
              - condition: true
                return: "default"
    """)
    wf = parse_workflow(yaml_str)
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_assign_next():
    yaml_str = textwrap.dedent("""\
        - check:
            switch:
              - condition: ${"key" in args}
                assign:
                  - value: ${args.key}
                next: process
        - process:
            return: ${value}
    """)
    wf = parse_workflow(yaml_str)
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_raise():
    yaml_str = textwrap.dedent("""\
        - check:
            switch:
              - condition: ${x < 0}
                raise: "x must be non-negative"
              - condition: true
                return: ${x}
    """)
    wf = parse_workflow(yaml_str)
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_over_50():
    conditions = "\n".join(
        f"      - condition: ${{x == {i}}}\n        next: step{i}" for i in range(51)
    )
    yaml_str = f"- check:\n    switch:\n{conditions}"
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)
