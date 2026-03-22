"""Tests for Workflow and Subworkflow.

Workflow composes Subworkflow(s) or inline steps into SimpleWorkflow or
SubworkflowsWorkflow.  Also tests backward-compatible WorkflowBuilder API.
"""

import pytest
import yaml

from cloud_workflows import (
    StepBuilder,
    Workflow,
    Subworkflow,
    WorkflowBuilder,
    expr,
)
from cloud_workflows.models import (
    SimpleWorkflow,
    SubworkflowsWorkflow,
    parse_workflow,
)
from conftest import load_fixture


# =============================================================================
# Simple workflow (single workflow, no params)
# =============================================================================


class TestSimpleWorkflow:
    """Single workflow via Workflow inline chaining produces SimpleWorkflow."""

    def test_inline_chain(self):
        w = Workflow().assign("init", x=10, y=20).returns("done", value=expr("x + y"))()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_single_main_with_params_produces_subworkflows(self):
        """Even a single workflow gets SubworkflowsWorkflow if it has params."""
        main = Subworkflow(params=["input"]).returns("done", value="ok")
        w = Workflow({"main": main}).build()
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Workflow with dict of Subworkflows
# =============================================================================


class TestSubworkflows:
    """Multiple Subworkflows produce SubworkflowsWorkflow."""

    def test_two_subworkflows(self):
        main = (
            Subworkflow()
            .call(
                "call_helper",
                func="helper",
                args={"input": "test"},
                result="res",
            )
            .returns("done", value=expr("res"))
        )
        helper = (
            Subworkflow(params=["input"])
            .call("log", func="sys.log", args={"text": expr("input")})
            .returns("done", value="ok")
        )
        w = Workflow({"main": main, "helper": helper})()
        assert isinstance(w, SubworkflowsWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "subworkflows.yaml"))
        assert w.to_dict() == expected

    def test_non_main_single_workflow(self):
        """Single workflow not named 'main' produces SubworkflowsWorkflow."""
        helper = Subworkflow().returns("done", value="ok")
        w = Workflow({"helper": helper})()
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Round-trip
# =============================================================================


class TestRoundTrip:
    """Build -> YAML -> parse -> compare."""

    def test_simple_round_trip(self):
        w1 = Workflow().assign("init", x=10).returns("done", value=expr("x"))()
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()

    def test_subworkflows_round_trip(self):
        main = (
            Subworkflow()
            .call("s1", func="helper", result="r")
            .returns("s2", value=expr("r"))
        )
        helper = Subworkflow().returns("s1", value="ok")
        w1 = Workflow({"main": main, "helper": helper})()
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()


# =============================================================================
# Error cases
# =============================================================================


class TestWorkflowErrors:
    """Error handling for Workflow."""

    def test_no_steps_and_no_dict_raises(self):
        with pytest.raises(ValueError):
            Workflow()()

    def test_empty_inline_chain_raises(self):
        """Workflow with no steps added inline should raise."""
        with pytest.raises(ValueError):
            Workflow()()

    def test_both_inline_and_dict_raises(self):
        """Cannot have both inline steps and a subworkflow dict."""
        sub = Subworkflow().returns("done", value="ok")
        w = Workflow({"main": sub})
        w.assign("init", x=1)
        with pytest.raises(ValueError):
            w()

    def test_empty_subworkflow_raises(self):
        with pytest.raises(ValueError, match="no steps"):
            Workflow({"main": Subworkflow()})()


# =============================================================================
# Backward compat: WorkflowBuilder
# =============================================================================


class TestWorkflowBuilderBackwardCompat:
    """WorkflowBuilder still works for backward compatibility."""

    def test_simple_workflow(self):
        steps = (
            StepBuilder()
            .assign("init", x=10, y=20)
            .returns("done", value=expr("x + y"))
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_steps_shorthand(self):
        sb = (
            StepBuilder()
            .assign("init", x=10, y=20)
            .returns("done", value=expr("x + y"))
        )
        w = WorkflowBuilder().steps(sb).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_steps_with_lambda(self):
        w = (
            WorkflowBuilder()
            .steps(
                lambda s: s.assign("init", x=10, y=20).returns(
                    "done", value=expr("x + y")
                )
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_workflow_with_lambda(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                lambda s: s.assign("init", x=10).returns("done", value=expr("x")),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        d = w.to_dict()
        assert d[0] == {"init": {"assign": [{"x": 10}]}}
        assert d[1] == {"done": {"return": "${x}"}}

    def test_no_workflows_raises(self):
        with pytest.raises(ValueError, match="No workflows"):
            WorkflowBuilder().build()

    def test_duplicate_workflow_name_raises(self):
        steps = StepBuilder().assign("s1", x=1)
        with pytest.raises(ValueError, match="Duplicate workflow name"):
            (WorkflowBuilder().workflow("main", steps).workflow("main", steps))

    def test_empty_step_builder_raises(self):
        with pytest.raises(ValueError, match="no steps"):
            WorkflowBuilder().workflow("main", StepBuilder()).build()


# =============================================================================
# Chaining
# =============================================================================


class TestWorkflowChaining:
    """Test that chaining returns self correctly."""

    def test_raw_returns_builder(self):
        b = StepBuilder()
        result = b.raw("s1", {"assign": [{"x": 1}]})
        assert result is b

    def test_workflow_inline_chain(self):
        w = (
            Workflow()
            .raw("s1", {"assign": [{"a": 1}]})
            .raw("s2", {"assign": [{"b": 2}]})
            .raw("s3", {"assign": [{"c": 3}]})
            .raw("s4", {"assign": [{"d": 4}]})
            .raw("s5", {"return": "${a + b + c + d}"})
        )()
        assert isinstance(w, SimpleWorkflow)
        assert len(w.steps) == 5
