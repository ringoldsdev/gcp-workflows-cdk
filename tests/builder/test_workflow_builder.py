"""Tests for Steps finalization and multi-workflow composition.

_finalize() converts a dict[str, Steps] to raw workflow data:
- Single "main" without params → list of step dicts (simple workflow)
- Multiple workflows or main with params → dict of workflow definitions
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
from cloud_workflows.builder import _finalize, _to_yaml
from cloud_workflows.models import parse_workflow
from conftest import load_fixture


# =============================================================================
# Simple workflow (single Steps, no params)
# =============================================================================


class TestSimpleWorkflow:
    """Single Steps container produces a simple workflow (list of step dicts)."""

    def test_simple_finalize(self):
        s = Steps()
        s.step("init", Assign(x=10, y=20))
        s.step("done", Return(expr("x + y")))
        w = _finalize({"main": s})
        assert isinstance(w, list)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w == expected

    def test_with_params_produces_subworkflows(self):
        """Steps with params produces dict even for single workflow."""
        s = Steps(params=["input"])
        s.step("done", Return("ok"))
        w = _finalize({"main": s})
        assert isinstance(w, dict)


# =============================================================================
# Multi-workflow (dict of Steps)
# =============================================================================


class TestMultiWorkflow:
    """Dict of Steps produces subworkflows dict."""

    def test_two_workflows(self):
        main = Steps()
        main.step(
            "call_helper",
            Call("helper", args={"input": "test"}, result="res"),
        )
        main.step("done", Return(expr("res")))

        helper = Steps(params=["input"])
        helper.step("log", Call("sys.log", args={"text": expr("input")}))
        helper.step("done", Return("ok"))

        w = _finalize({"main": main, "helper": helper})
        assert isinstance(w, dict)
        expected = yaml.safe_load(load_fixture("cdk", "subworkflows.yaml"))
        assert w == expected

    def test_single_main_no_params(self):
        """Single 'main' without params -> list (simple workflow)."""
        main = Steps()
        main.step("done", Return("ok"))
        w = _finalize({"main": main})
        assert isinstance(w, list)

    def test_non_main_requires_main_key(self):
        """Dict without 'main' key raises ValueError."""
        helper = Steps()
        helper.step("done", Return("ok"))
        with pytest.raises(ValueError, match="'main' key"):
            _finalize({"helper": helper})


# =============================================================================
# Round-trip
# =============================================================================


class TestRoundTrip:
    """Build -> YAML -> parse -> compare."""

    def test_simple_round_trip(self):
        s = Steps()
        s.step("init", Assign(x=10))
        s.step("done", Return(expr("x")))
        w1 = _finalize({"main": s})
        w2 = parse_workflow(_to_yaml(w1))
        assert w1 == w2.to_dict()

    def test_multi_workflow_round_trip(self):
        main = Steps()
        main.step("s1", Call("helper", result="r"))
        main.step("s2", Return(expr("r")))

        helper = Steps()
        helper.step("s1", Return("ok"))

        w1 = _finalize({"main": main, "helper": helper})
        w2 = parse_workflow(_to_yaml(w1))
        assert w1 == w2.to_dict()


# =============================================================================
# Error cases
# =============================================================================


class TestErrors:
    """Error handling for finalization."""

    def test_empty_steps_raises(self):
        s = Steps()
        with pytest.raises(ValueError, match="no steps"):
            _finalize({"main": s})

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

    def test_missing_main_key_raises(self):
        """Dict without 'main' key raises ValueError."""
        helper = Steps()
        helper.step("done", Return("ok"))
        with pytest.raises(ValueError, match="'main' key"):
            _finalize({"helper": helper})
