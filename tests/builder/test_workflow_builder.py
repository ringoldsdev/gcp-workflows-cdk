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
from conftest import load_fixture, assert_workflow_match_fixture


# =============================================================================
# Simple workflow (single Steps, no params)
# =============================================================================


class TestSimpleWorkflow:
    """Single Steps container produces a simple workflow (list of step dicts)."""

    def test_simple_finalize(self, tmp_path):
        s = Steps()
        s.step("init", Assign(x=10, y=20))
        s.step("done", Return(expr("x + y")))
        assert_workflow_match_fixture(
            {"main": s}, "cdk", "simple_assign.yaml", tmp_path=tmp_path
        )

    def test_with_params_produces_subworkflows(self):
        """Steps with params produces dict even for single workflow."""
        s = Steps(params=["input"])
        s.step("done", Return("ok"))
        w = _finalize({"main": s})
        assert isinstance(w, dict)

    def test_single_main_no_params_is_list(self):
        """Single 'main' without params -> list (simple workflow)."""
        main = Steps()
        main.step("done", Return("ok"))
        w = _finalize({"main": main})
        assert isinstance(w, list)

    def test_finalize_single_main_fixture(self, tmp_path):
        """Single main produces the expected YAML via fixture comparison."""
        main = Steps()
        main.step("done", Return("ok"))
        assert_workflow_match_fixture(
            {"main": main}, "cdk", "finalize_single_main.yaml", tmp_path=tmp_path
        )

    def test_finalize_with_params_fixture(self, tmp_path):
        """Main with params produces dict-form YAML."""
        main = Steps(params=["input"])
        main.step("done", Return("ok"))
        assert_workflow_match_fixture(
            {"main": main}, "cdk", "finalize_params.yaml", tmp_path=tmp_path
        )


# =============================================================================
# Multi-workflow (dict of Steps)
# =============================================================================


class TestMultiWorkflow:
    """Dict of Steps produces subworkflows dict."""

    def test_two_workflows(self, tmp_path):
        main = Steps()
        main.step(
            "call_helper",
            Call("helper", args={"input": "test"}, result="res"),
        )
        main.step("done", Return(expr("res")))

        helper = Steps(params=["input"])
        helper.step("log", Call("sys.log", args={"text": expr("input")}))
        helper.step("done", Return("ok"))

        assert_workflow_match_fixture(
            {"main": main, "helper": helper},
            "cdk",
            "subworkflows.yaml",
            tmp_path=tmp_path,
        )

    def test_two_workflows_is_dict(self):
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

    def test_simple_round_trip(self, tmp_path):
        s = Steps()
        s.step("init", Assign(x=10))
        s.step("done", Return(expr("x")))
        assert_workflow_match_fixture(
            {"main": s}, "cdk", "roundtrip_simple.yaml", tmp_path=tmp_path
        )

    def test_multi_workflow_round_trip(self, tmp_path):
        main = Steps()
        main.step("s1", Call("helper", result="r"))
        main.step("s2", Return(expr("r")))

        helper = Steps()
        helper.step("s1", Return("ok"))

        assert_workflow_match_fixture(
            {"main": main, "helper": helper},
            "cdk",
            "roundtrip_multi.yaml",
            tmp_path=tmp_path,
        )

    def test_simple_parse_round_trip(self):
        """Build → YAML → parse → to_dict matches original finalized data."""
        s = Steps()
        s.step("init", Assign(x=10))
        s.step("done", Return(expr("x")))
        w1 = _finalize({"main": s})
        w2 = parse_workflow(_to_yaml(w1))
        assert w1 == w2.to_dict()

    def test_multi_parse_round_trip(self):
        """Multi-workflow Build → YAML → parse → to_dict matches original."""
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
