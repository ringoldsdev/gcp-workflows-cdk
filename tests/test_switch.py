import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, SwitchStep
from conftest import parse_fixture


def test_switch_basic():
    wf = parse_fixture("switch", "basic.yaml")
    switch_step = wf.steps[1]
    assert isinstance(switch_step.body, SwitchStep)
    assert len(switch_step.body.switch) == 2


def test_switch_fallthrough():
    wf = parse_fixture("switch", "fallthrough.yaml")
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)
    assert switch_step.body.next == "positive"


def test_switch_embedded_steps():
    wf = parse_fixture("switch", "embedded_steps.yaml")
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_assign_next():
    wf = parse_fixture("switch", "assign_next.yaml")
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_raise():
    wf = parse_fixture("switch", "raise.yaml")
    switch_step = wf.steps[0]
    assert isinstance(switch_step.body, SwitchStep)


def test_switch_over_50():
    with pytest.raises(ValidationError):
        parse_fixture("switch", "over_50.yaml")
