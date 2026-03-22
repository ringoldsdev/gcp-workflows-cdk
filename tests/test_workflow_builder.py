"""Tests for WorkflowBuilder.

WorkflowBuilder composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow.
"""

import pytest
import yaml

from cloud_workflows import (
    StepBuilder,
    WorkflowBuilder,
    analyze_workflow,
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
    """Single workflow named 'main' without params produces SimpleWorkflow."""

    def test_single_main_workflow(self):
        steps = (
            StepBuilder()
            .step("init", "assign", x=10, y=20)
            .step("done", "return", value=expr("x + y"))
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_single_main_with_params_produces_subworkflows(self):
        """Even a single workflow gets SubworkflowsWorkflow if it has params."""
        steps = StepBuilder().step("done", "return", value="ok")
        w = WorkflowBuilder().workflow("main", steps, params=["input"]).build()
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Subworkflows
# =============================================================================


class TestSubworkflows:
    """Multiple workflows produce SubworkflowsWorkflow."""

    def test_two_workflows(self):
        main = (
            StepBuilder()
            .step(
                "call_helper",
                "call",
                func="helper",
                args={"input": "test"},
                result="res",
            )
            .step("done", "return", value=expr("res"))
        )
        helper = (
            StepBuilder()
            .step("log", "call", func="sys.log", args={"text": expr("input")})
            .step("done", "return", value="ok")
        )
        w = (
            WorkflowBuilder()
            .workflow("main", main)
            .workflow("helper", helper, params=["input"])
            .build()
        )
        assert isinstance(w, SubworkflowsWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "subworkflows.yaml"))
        assert w.to_dict() == expected

    def test_non_main_single_workflow(self):
        """Single workflow not named 'main' produces SubworkflowsWorkflow."""
        steps = StepBuilder().step("done", "return", value="ok")
        w = WorkflowBuilder().workflow("helper", steps).build()
        assert isinstance(w, SubworkflowsWorkflow)


# =============================================================================
# Round-trip
# =============================================================================


class TestRoundTrip:
    """Build → YAML → parse → compare."""

    def test_simple_round_trip(self):
        steps = (
            StepBuilder()
            .step("init", "assign", x=10)
            .step("done", "return", value=expr("x"))
        )
        w1 = WorkflowBuilder().workflow("main", steps).build()
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()

    def test_subworkflows_round_trip(self):
        main = (
            StepBuilder()
            .step("s1", "call", func="helper", result="r")
            .step("s2", "return", value=expr("r"))
        )
        helper = StepBuilder().step("s1", "return", value="ok")
        w1 = WorkflowBuilder().workflow("main", main).workflow("helper", helper).build()
        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()


# =============================================================================
# Validation integration
# =============================================================================


class TestWorkflowValidation:
    """WorkflowBuilder output passes the full analysis pipeline."""

    def test_simple_validates(self):
        steps = (
            StepBuilder()
            .step("init", "assign", x=10, y=20)
            .step("done", "return", value=expr("x + y"))
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        result = analyze_workflow(w)
        assert result.is_valid

    def test_subworkflows_validates(self):
        main = (
            StepBuilder()
            .step(
                "call_helper",
                "call",
                func="helper",
                args={"input": "test"},
                result="res",
            )
            .step("done", "return", value=expr("res"))
        )
        helper = (
            StepBuilder()
            .step("log", "call", func="sys.log", args={"text": expr("input")})
            .step("done", "return", value="ok")
        )
        w = (
            WorkflowBuilder()
            .workflow("main", main)
            .workflow("helper", helper, params=["input"])
            .build()
        )
        result = analyze_workflow(w)
        assert result.is_valid


# =============================================================================
# Error cases
# =============================================================================


class TestWorkflowBuilderErrors:
    """Error handling for WorkflowBuilder."""

    def test_no_workflows_raises(self):
        with pytest.raises(ValueError, match="No workflows"):
            WorkflowBuilder().build()

    def test_duplicate_workflow_name_raises(self):
        steps = StepBuilder().step("s1", "assign", x=1)
        with pytest.raises(ValueError, match="Duplicate workflow name"):
            (WorkflowBuilder().workflow("main", steps).workflow("main", steps))

    def test_empty_step_builder_raises(self):
        with pytest.raises(ValueError, match="no steps"):
            WorkflowBuilder().workflow("main", StepBuilder()).build()
