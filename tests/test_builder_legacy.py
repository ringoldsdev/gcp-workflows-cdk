"""Tests for the builder with raw passthrough patterns.

These tests verify that StepBuilder.raw() works correctly with both
Pydantic model instances and raw dicts, producing correct output.

Each test class builds a workflow using the builder and verifies:
1. The correct workflow type is returned
2. The serialized YAML matches the expected fixture
3. Both model-based and dict-based construction produce the same result
"""

import pytest
import yaml

from cloud_workflows import StepBuilder, WorkflowBuilder, analyze_workflow, expr
from cloud_workflows.models import (
    AssignStep,
    BackoffConfig,
    Branch,
    CallStep,
    ExceptBody,
    ForBody,
    ForStep,
    NestedStepsStep,
    ParallelBody,
    ParallelStep,
    RaiseStep,
    RetryConfig,
    ReturnStep,
    SimpleWorkflow,
    SubworkflowsWorkflow,
    SwitchCondition,
    SwitchStep,
    TryCallBody,
    TryStep,
)
from conftest import load_fixture


class TestSimpleAssignBuilder:
    """Build a simple assign + return workflow using raw passthrough."""

    def test_with_models(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
                .raw("done", ReturnStep(return_="${x + y}")),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", {"assign": [{"x": 10}, {"y": 20}]})
                .raw("done", {"return": "${x + y}"}),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert w.to_dict() == expected

    def test_models_and_dicts_match(self):
        w_models = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
                .raw("done", ReturnStep(return_="${x + y}")),
            )
            .build()
        )
        w_dicts = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", {"assign": [{"x": 10}, {"y": 20}]})
                .raw("done", {"return": "${x + y}"}),
            )
            .build()
        )
        assert w_models.to_dict() == w_dicts.to_dict()

    def test_analyze(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
                .raw("done", ReturnStep(return_="${x + y}")),
            )
            .build()
        )
        result = analyze_workflow(w)
        assert result.is_valid


class TestSubworkflowsBuilder:
    """Build a subworkflows workflow using raw passthrough."""

    def test_with_models(self):
        main = (
            StepBuilder()
            .raw(
                "call_helper",
                CallStep(call="helper", args={"input": "test"}, result="res"),
            )
            .raw("done", ReturnStep(return_="${res}"))
        )
        helper = (
            StepBuilder()
            .raw(
                "log",
                CallStep(call="sys.log", args={"text": "${input}"}),
            )
            .raw("done", ReturnStep(return_="ok"))
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

    def test_with_dicts(self):
        main = (
            StepBuilder()
            .raw(
                "call_helper",
                {"call": "helper", "args": {"input": "test"}, "result": "res"},
            )
            .raw("done", {"return": "${res}"})
        )
        helper = (
            StepBuilder()
            .raw("log", {"call": "sys.log", "args": {"text": "${input}"}})
            .raw("done", {"return": "ok"})
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

    def test_analyze(self):
        main = (
            StepBuilder()
            .raw(
                "call_helper",
                CallStep(call="helper", args={"input": "test"}, result="res"),
            )
            .raw("done", ReturnStep(return_="${res}"))
        )
        helper = (
            StepBuilder()
            .raw("log", CallStep(call="sys.log", args={"text": "${input}"}))
            .raw("done", ReturnStep(return_="ok"))
        )
        w = (
            WorkflowBuilder()
            .workflow("main", main)
            .workflow("helper", helper, params=["input"])
            .build()
        )
        result = analyze_workflow(w)
        assert result.is_valid


class TestForLoopBuilder:
    """Build a for loop workflow using raw passthrough."""

    def test_with_models(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "loop",
                    ForStep(
                        for_=ForBody(
                            value="item",
                            in_=["a", "b", "c"],
                            steps=[
                                {
                                    "log": {
                                        "call": "sys.log",
                                        "args": {"text": "${item}"},
                                    }
                                }
                            ],
                        )
                    ),
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "loop",
                    {
                        "for": {
                            "value": "item",
                            "in": ["a", "b", "c"],
                            "steps": [
                                {
                                    "log": {
                                        "call": "sys.log",
                                        "args": {"text": "${item}"},
                                    }
                                }
                            ],
                        }
                    },
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert w.to_dict() == expected


class TestSwitchBuilder:
    """Build a switch workflow using raw passthrough."""

    def test_with_models(self):
        steps = (
            StepBuilder()
            .raw("init", AssignStep(assign=[{"x": 10}]))
            .raw(
                "check",
                SwitchStep(
                    switch=[
                        SwitchCondition(condition="${x > 0}", next="positive"),
                        SwitchCondition(condition=True, next="negative"),
                    ]
                ),
            )
            .raw("positive", ReturnStep(return_="positive"))
            .raw("negative", ReturnStep(return_="negative"))
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        steps = (
            StepBuilder()
            .raw("init", {"assign": [{"x": 10}]})
            .raw(
                "check",
                {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                        {"condition": True, "next": "negative"},
                    ]
                },
            )
            .raw("positive", {"return": "positive"})
            .raw("negative", {"return": "negative"})
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert w.to_dict() == expected


class TestParallelBranchesBuilder:
    """Build a parallel branches workflow using raw passthrough."""

    def test_with_models(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "parallel_work",
                    ParallelStep(
                        parallel=ParallelBody(
                            branches=[
                                Branch(
                                    name="branch1",
                                    steps=[
                                        {
                                            "b1_step": {
                                                "call": "sys.log",
                                                "args": {"text": "branch1"},
                                            }
                                        }
                                    ],
                                ),
                                Branch(
                                    name="branch2",
                                    steps=[
                                        {
                                            "b2_step": {
                                                "call": "sys.log",
                                                "args": {"text": "branch2"},
                                            }
                                        }
                                    ],
                                ),
                            ]
                        )
                    ),
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "parallel_work",
                    {
                        "parallel": {
                            "branches": [
                                {
                                    "branch1": {
                                        "steps": [
                                            {
                                                "b1_step": {
                                                    "call": "sys.log",
                                                    "args": {"text": "branch1"},
                                                }
                                            }
                                        ]
                                    }
                                },
                                {
                                    "branch2": {
                                        "steps": [
                                            {
                                                "b2_step": {
                                                    "call": "sys.log",
                                                    "args": {"text": "branch2"},
                                                }
                                            }
                                        ]
                                    }
                                },
                            ]
                        }
                    },
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert w.to_dict() == expected


class TestTryExceptRetryBuilder:
    """Build a try/except/retry workflow using raw passthrough."""

    def test_with_models(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "try_call",
                    TryStep(
                        try_=TryCallBody(
                            call="http.get",
                            args={"url": "https://example.com"},
                            result="response",
                        ),
                        retry=RetryConfig(
                            predicate="${e.code == 429}",
                            max_retries=3,
                            backoff=BackoffConfig(
                                initial_delay=1, max_delay=30, multiplier=2
                            ),
                        ),
                        except_=ExceptBody(
                            as_="e",
                            steps=[{"handle": {"raise": "${e}"}}],
                        ),
                    ),
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder().raw(
                    "try_call",
                    {
                        "try": {
                            "call": "http.get",
                            "args": {"url": "https://example.com"},
                            "result": "response",
                        },
                        "retry": {
                            "predicate": "${e.code == 429}",
                            "max_retries": 3,
                            "backoff": {
                                "initial_delay": 1,
                                "max_delay": 30,
                                "multiplier": 2,
                            },
                        },
                        "except": {
                            "as": "e",
                            "steps": [{"handle": {"raise": "${e}"}}],
                        },
                    },
                ),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert w.to_dict() == expected


class TestNestedStepsBuilder:
    """Build a nested steps workflow using raw passthrough."""

    def test_with_models(self):
        steps = (
            StepBuilder()
            .raw(
                "group",
                NestedStepsStep(
                    steps=[
                        {"step_a": {"call": "sys.log", "args": {"text": "a"}}},
                        {"step_b": {"call": "sys.log", "args": {"text": "b"}}},
                    ],
                    next="done",
                ),
            )
            .raw("done", ReturnStep(return_="ok"))
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert w.to_dict() == expected

    def test_with_dicts(self):
        steps = (
            StepBuilder()
            .raw(
                "group",
                {
                    "steps": [
                        {"step_a": {"call": "sys.log", "args": {"text": "a"}}},
                        {"step_b": {"call": "sys.log", "args": {"text": "b"}}},
                    ],
                    "next": "done",
                },
            )
            .raw("done", {"return": "ok"})
        )
        w = WorkflowBuilder().workflow("main", steps).build()
        assert isinstance(w, SimpleWorkflow)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert w.to_dict() == expected


class TestBuilderValidation:
    """Test builder error handling."""

    def test_build_empty_raises(self):
        with pytest.raises(ValueError, match="No workflows defined"):
            WorkflowBuilder().build()

    def test_build_empty_workflow_raises(self):
        with pytest.raises(ValueError, match="has no steps"):
            WorkflowBuilder().workflow("main", StepBuilder()).build()

    def test_duplicate_workflow_name_raises(self):
        with pytest.raises(ValueError, match="Duplicate workflow name"):
            (
                WorkflowBuilder()
                .workflow("main", StepBuilder().raw("s1", {"assign": [{"x": 1}]}))
                .workflow("main", StepBuilder().raw("s2", {"assign": [{"y": 2}]}))
            )

    def test_invalid_step_body_raises(self):
        with pytest.raises(Exception):
            WorkflowBuilder().workflow(
                "main",
                StepBuilder().raw("bad", {"invalid_key": 42}),
            ).build()

    def test_pydantic_validation_in_builder(self):
        """Pydantic validation runs eagerly at model construction time."""
        with pytest.raises(Exception):
            StepBuilder().raw("bad", AssignStep(assign=[]))


class TestBuilderExprHelper:
    """Test builder with expr() helper."""

    def test_expr_in_model(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", AssignStep(assign=[{"x": 1}]))
                .raw("done", ReturnStep(return_=expr("x + 1"))),
            )
            .build()
        )
        assert w.to_dict() == [
            {"init": {"assign": [{"x": 1}]}},
            {"done": {"return": "${x + 1}"}},
        ]

    def test_expr_in_dict(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", {"assign": [{"x": 1}]})
                .raw("done", {"return": expr("x + 1")}),
            )
            .build()
        )
        assert w.to_dict() == [
            {"init": {"assign": [{"x": 1}]}},
            {"done": {"return": "${x + 1}"}},
        ]


class TestBuilderChaining:
    """Test that chaining returns self correctly."""

    def test_raw_returns_builder(self):
        b = StepBuilder()
        result = b.raw("s1", {"assign": [{"x": 1}]})
        assert result is b

    def test_workflow_returns_builder(self):
        b = WorkflowBuilder()
        result = b.workflow("main", StepBuilder().raw("s1", {"assign": [{"x": 1}]}))
        assert result is b

    def test_long_chain(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("s1", {"assign": [{"a": 1}]})
                .raw("s2", {"assign": [{"b": 2}]})
                .raw("s3", {"assign": [{"c": 3}]})
                .raw("s4", {"assign": [{"d": 4}]})
                .raw("s5", {"return": "${a + b + c + d}"}),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        assert len(w.steps) == 5


class TestBuilderRoundTrip:
    """Build with builder, serialize to YAML, parse back, compare."""

    def test_simple_round_trip(self):
        w1 = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("init", {"assign": [{"x": 10}]})
                .raw("done", {"return": "${x}"}),
            )
            .build()
        )
        from cloud_workflows.models import parse_workflow

        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()

    def test_subworkflows_round_trip(self):
        main = (
            StepBuilder()
            .raw("s1", {"call": "helper", "result": "r"})
            .raw("s2", {"return": "${r}"})
        )
        helper = StepBuilder().raw("s1", {"return": "ok"})
        w1 = WorkflowBuilder().workflow("main", main).workflow("helper", helper).build()
        from cloud_workflows.models import parse_workflow

        w2 = parse_workflow(w1.to_yaml())
        assert w1.to_dict() == w2.to_dict()


class TestMixedConstruction:
    """Test mixing model and dict body types in the same chain."""

    def test_mixed_models_and_dicts(self):
        w = (
            WorkflowBuilder()
            .workflow(
                "main",
                StepBuilder()
                .raw("s1", AssignStep(assign=[{"x": 1}]))
                .raw("s2", {"call": "sys.log", "args": {"text": "${x}"}})
                .raw("s3", ReturnStep(return_="${x}")),
            )
            .build()
        )
        assert isinstance(w, SimpleWorkflow)
        assert len(w.steps) == 3
        d = w.to_dict()
        assert d[0] == {"s1": {"assign": [{"x": 1}]}}
        assert d[1] == {"s2": {"call": "sys.log", "args": {"text": "${x}"}}}
        assert d[2] == {"s3": {"return": "${x}"}}
