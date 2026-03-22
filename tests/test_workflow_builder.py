"""Tests for WorkflowBuilder and the run() convention.

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


# =============================================================================
# run() convention
# =============================================================================


class TestRunConvention:
    """The run() convention: a function returning list[tuple[str, Workflow]]."""

    def test_run_returns_list_of_tuples(self):
        """Simulate what a workflow definition file's run() would return."""

        def run():
            steps = (
                StepBuilder()
                .step("init", "assign", x=10)
                .step("done", "return", value=expr("x"))
            )
            w = WorkflowBuilder().workflow("main", steps).build()
            return [("my_workflow.yaml", w)]

        result = run()
        assert isinstance(result, list)
        assert len(result) == 1
        filename, workflow = result[0]
        assert filename == "my_workflow.yaml"
        assert isinstance(workflow, SimpleWorkflow)

    def test_run_multiple_workflows(self):
        """A single file can define multiple output workflows."""

        def run():
            steps1 = StepBuilder().step("done", "return", value="ok")
            steps2 = StepBuilder().step("done", "return", value="also ok")
            return [
                ("flow1.yaml", WorkflowBuilder().workflow("main", steps1).build()),
                ("flow2.yaml", WorkflowBuilder().workflow("main", steps2).build()),
            ]

        result = run()
        assert len(result) == 2
        assert result[0][0] == "flow1.yaml"
        assert result[1][0] == "flow2.yaml"

    def test_run_with_composable_steps(self):
        """Demonstrate composability via StepBuilder.apply()."""

        def common_setup() -> StepBuilder:
            return StepBuilder().step("setup", "assign", initialized=True)

        def run():
            steps = (
                StepBuilder()
                .apply(common_setup())
                .step("done", "return", value=expr("initialized"))
            )
            return [
                ("composed.yaml", WorkflowBuilder().workflow("main", steps).build())
            ]

        result = run()
        filename, workflow = result[0]
        assert isinstance(workflow, SimpleWorkflow)
        d = workflow.to_dict()
        assert d[0] == {"setup": {"assign": [{"initialized": True}]}}
