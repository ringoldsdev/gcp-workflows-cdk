"""Tests for Steps finalization and multi-workflow composition.

Steps can be finalized into SimpleWorkflow (no params) or
SubworkflowsWorkflow (with params or multi-workflow dict).
"""

import pytest
import yaml

from cloud_workflows import (
    Steps,
    Assign,
    Call,
    Return,
    expr,
)
from cloud_workflows.builder import _finalize
from cloud_workflows.models import (
    SimpleWorkflow,
    SubworkflowsWorkflow,
    parse_workflow,
)
from conftest import load_fixture


# =============================================================================
# Simple workflow (single Steps, no params)
# =============================================================================


class TestSimpleWorkflow:
    """Single Steps container produces SimpleWorkflow."""

    def test_simple_finalize(self):
        s = Steps()
        s("init", Assign(x=10, y=20))
        s("done", Return(expr("x + y")))
        w = s._finalize()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_with_params_produces_subworkflows(self):
        """Steps with params produces SubworkflowsWorkflow even for single workflow."""
        s = Steps(params=["input"])
        s("done", Return("ok"))
        w = s._finalize()
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Multi-workflow (dict of Steps)
# =============================================================================


class TestMultiWorkflow:
    """Dict of Steps produces SubworkflowsWorkflow."""

    def test_two_workflows(self):
        main = Steps()
        main(
            "call_helper",
            Call("helper", args={"input": "test"}, result="res"),
        )
        main("done", Return(expr("res")))

        helper = Steps(params=["input"])
        helper("log", Call("sys.log", args={"text": expr("input")}))
        helper("done", Return("ok"))

        w = _finalize({"main": main, "helper": helper})
        assert isinstance(w, SubworkflowsWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "subworkflows.yaml"))
        assert w.to_dict() == expected

    def test_single_main_no_params(self):
        """Single 'main' without params → SimpleWorkflow."""
        main = Steps()
        main("done", Return("ok"))
        w = _finalize({"main": main})
        assert isinstance(w, SimpleWorkflow)

    def test_non_main_single_workflow(self):
        """Single workflow not named 'main' → SubworkflowsWorkflow."""
        helper = Steps()
        helper("done", Return("ok"))
        w = _finalize({"helper": helper})
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Round-trip
# =============================================================================


class TestRoundTrip:
    """Build → YAML → parse → compare."""

    def test_simple_round_trip(self):
        s = Steps()
        s("init", Assign(x=10))
        s("done", Return(expr("x")))
        w1 = s._finalize()
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()

    def test_multi_workflow_round_trip(self):
        main = Steps()
        main("s1", Call("helper", result="r"))
        main("s2", Return(expr("r")))

        helper = Steps()
        helper("s1", Return("ok"))

        w1 = _finalize({"main": main, "helper": helper})
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()


# =============================================================================
# Error cases
# =============================================================================


class TestErrors:
    """Error handling for finalization."""

    def test_empty_steps_raises(self):
        s = Steps()
        with pytest.raises(ValueError, match="No steps"):
            s._finalize()

    def test_empty_workflow_in_dict_raises(self):
        main = Steps()
        with pytest.raises(ValueError, match="no steps"):
            _finalize({"main": main})

    def test_wrong_type_in_dict_raises(self):
        with pytest.raises(TypeError, match="Steps instances"):
            _finalize({"main": "not steps"})  # type: ignore[dict-item]

    def test_wrong_type_raises(self):
        with pytest.raises(TypeError):
            _finalize(42)  # type: ignore[arg-type]
