"""Tests for StepBuilder and step sub-builder classes.

Tests are organized by:
1. Each step type with all input forms (kwargs, lambda, model passthrough via .raw())
2. Sub-builder .apply() for each step type
3. StepBuilder.apply() for composing step sequences
4. Error cases

Each test builds steps, serializes to dict, and compares against expected output.
"""

import pytest
import yaml

from cloud_workflows import (
    StepBuilder,
    WorkflowBuilder,
    analyze_workflow,
    expr,
)
from cloud_workflows.steps import (
    Assign,
    Call,
    Return_,
    Raise_,
    Switch,
    For,
    Parallel,
    Try_,
    Steps,
)
from cloud_workflows.models import (
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SwitchStep,
    SwitchCondition,
    ForStep,
    ForBody,
    ParallelStep,
    ParallelBody,
    Branch,
    TryStep,
    TryCallBody,
    ExceptBody,
    RetryConfig,
    BackoffConfig,
    NestedStepsStep,
    SimpleWorkflow,
)
from conftest import load_fixture


# =============================================================================
# Helper: build a SimpleWorkflow from a StepBuilder for comparison
# =============================================================================


def _to_dict(sb: StepBuilder) -> list:
    """Build steps into a SimpleWorkflow and serialize to dict."""
    w = WorkflowBuilder().workflow("main", sb).build()
    assert isinstance(w, SimpleWorkflow)
    return w.to_dict()


# =============================================================================
# Assign step
# =============================================================================


class TestAssignKwargs:
    """Assign step via kwargs."""

    def test_simple_assign(self):
        sb = StepBuilder().assign("init", x=10, y=20)
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_assign_with_expr(self):
        sb = StepBuilder().assign("init", x=10, y=expr("x + 1"))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": "${x + 1}"}]}}]

    def test_assign_with_items_kwarg(self):
        """The 'items' kwarg passes a raw list of dicts for complex keys."""
        sb = StepBuilder().assign(
            "init",
            items=[{"x": 10}, {'map["key"]': "value"}],
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {'map["key"]': "value"}]}}]


class TestAssignLambda:
    """Assign step via lambda configurator."""

    def test_lambda_set(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).set("y", 20),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_lambda_items(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.items([{"x": 10}, {"y": 20}]),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_lambda_with_next(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).next("done"),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}], "next": "done"}}]


class TestAssignPassthrough:
    """Assign step via Pydantic model or dict passthrough (.raw())."""

    def test_pydantic_model(self):
        sb = StepBuilder().raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_dict_passthrough(self):
        sb = StepBuilder().raw("init", {"assign": [{"x": 10}, {"y": 20}]})
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]


class TestAssignSubBuilder:
    """Assign sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("init", Assign().set("x", 10).set("y", 20))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]


class TestAssignFixture:
    """Assign step matches YAML fixture."""

    def test_simple_assign_fixture(self):
        sb = (
            StepBuilder()
            .assign("init", x=10, y=20)
            .return_("done", value=expr("x + y"))
        )
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert _to_dict(sb) == expected

    def test_all_three_forms_match(self):
        """kwargs, lambda, and model passthrough all produce the same output."""
        sb_kwargs = StepBuilder().assign("init", x=10, y=20)
        sb_lambda = StepBuilder().assign("init", lambda a: a.set("x", 10).set("y", 20))
        sb_model = StepBuilder().raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
        assert _to_dict(sb_kwargs) == _to_dict(sb_lambda) == _to_dict(sb_model)


# =============================================================================
# Call step
# =============================================================================


class TestCallKwargs:
    """Call step via kwargs."""

    def test_simple_call(self):
        sb = StepBuilder().call("log", func="sys.log", args={"text": "hello"})
        d = _to_dict(sb)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]

    def test_call_with_result(self):
        sb = StepBuilder().call(
            "fetch",
            func="http.get",
            args={"url": "https://example.com"},
            result="resp",
        )
        d = _to_dict(sb)
        assert d == [
            {
                "fetch": {
                    "call": "http.get",
                    "args": {"url": "https://example.com"},
                    "result": "resp",
                }
            }
        ]

    def test_call_with_next(self):
        sb = StepBuilder().call(
            "log",
            func="sys.log",
            args={"text": "hello"},
            next="done",
        )
        d = _to_dict(sb)
        assert d == [
            {"log": {"call": "sys.log", "args": {"text": "hello"}, "next": "done"}}
        ]


class TestCallLambda:
    """Call step via lambda configurator."""

    def test_lambda_call(self):
        sb = StepBuilder().call(
            "log",
            lambda c: c.func("sys.log").args(text="hello"),
        )
        d = _to_dict(sb)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]

    def test_lambda_call_with_result(self):
        sb = StepBuilder().call(
            "fetch",
            lambda c: c.func("http.get").args(url="https://example.com").result("resp"),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "fetch": {
                    "call": "http.get",
                    "args": {"url": "https://example.com"},
                    "result": "resp",
                }
            }
        ]


class TestCallSubBuilder:
    """Call sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("log", Call("sys.log").args(text="hello"))
        d = _to_dict(sb)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]


class TestCallPassthrough:
    """Call step via Pydantic model passthrough (.raw())."""

    def test_pydantic_model(self):
        sb = StepBuilder().raw(
            "log",
            CallStep(call="sys.log", args={"text": "hello"}),
        )
        d = _to_dict(sb)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]


# =============================================================================
# Return step
# =============================================================================


class TestReturnKwargs:
    """Return step via kwargs."""

    def test_return_value(self):
        sb = StepBuilder().return_("done", value="ok")
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]

    def test_return_expr(self):
        sb = StepBuilder().return_("done", value=expr("x + y"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "${x + y}"}}]


class TestReturnLambda:
    """Return step via lambda configurator."""

    def test_lambda_return(self):
        sb = StepBuilder().return_("done", lambda r: r.value("ok"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]


class TestReturnSubBuilder:
    """Return sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("done", Return_(expr("x + y")))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "${x + y}"}}]


class TestReturnPassthrough:
    """Return step via Pydantic model passthrough (.raw())."""

    def test_pydantic_model(self):
        sb = StepBuilder().raw("done", ReturnStep(return_="ok"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]


# =============================================================================
# Raise step
# =============================================================================


class TestRaiseKwargs:
    """Raise step via kwargs."""

    def test_raise_string(self):
        sb = StepBuilder().raise_("fail", value="something went wrong")
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": "something went wrong"}}]

    def test_raise_dict(self):
        sb = StepBuilder().raise_("fail", value={"code": 404, "message": "not found"})
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": {"code": 404, "message": "not found"}}}]


class TestRaiseLambda:
    """Raise step via lambda configurator."""

    def test_lambda_raise(self):
        sb = StepBuilder().raise_("fail", lambda r: r.value(expr("e")))
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": "${e}"}}]


class TestRaiseSubBuilder:
    """Raise sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("fail", Raise_({"code": 404}))
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": {"code": 404}}}]


# =============================================================================
# Switch step
# =============================================================================


class TestSwitchKwargs:
    """Switch step via kwargs."""

    def test_switch_conditions(self):
        sb = StepBuilder().switch(
            "check",
            conditions=[
                {"condition": expr("x > 0"), "next": "positive"},
                {"condition": True, "next": "negative"},
            ],
        )
        d = _to_dict(sb)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                        {"condition": True, "next": "negative"},
                    ]
                }
            }
        ]


class TestSwitchLambda:
    """Switch step via lambda configurator."""

    def test_lambda_switch(self):
        sb = StepBuilder().switch(
            "check",
            lambda s: (
                s.condition(expr("x > 0"), next="positive").condition(
                    True, next="negative"
                )
            ),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                        {"condition": True, "next": "negative"},
                    ]
                }
            }
        ]

    def test_lambda_switch_with_next(self):
        sb = StepBuilder().switch(
            "check",
            lambda s: (s.condition(expr("x > 0"), next="positive").next("fallback")),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                    ],
                    "next": "fallback",
                }
            }
        ]


class TestSwitchSubBuilder:
    """Switch sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw(
            "check",
            Switch()
            .condition(expr("x > 0"), next="positive")
            .condition(True, next="negative"),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                        {"condition": True, "next": "negative"},
                    ]
                }
            }
        ]


class TestSwitchFixture:
    """Switch step matches YAML fixture."""

    def test_switch_fixture(self):
        sb = (
            StepBuilder()
            .assign("init", x=10)
            .switch(
                "check",
                lambda s: (
                    s.condition(expr("x > 0"), next="positive").condition(
                        True, next="negative"
                    )
                ),
            )
            .return_("positive", value="positive")
            .return_("negative", value="negative")
        )
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert _to_dict(sb) == expected


# =============================================================================
# For step
# =============================================================================


class TestForKwargs:
    """For step via kwargs."""

    def test_for_in(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().for_(
            "loop",
            value="item",
            in_=["a", "b", "c"],
            steps=inner,
        )
        d = _to_dict(sb)
        assert d == [
            {
                "loop": {
                    "for": {
                        "value": "item",
                        "in": ["a", "b", "c"],
                        "steps": [
                            {"log": {"call": "sys.log", "args": {"text": "${item}"}}}
                        ],
                    }
                }
            }
        ]


class TestForLambda:
    """For step via lambda configurator."""

    def test_lambda_for(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().for_(
            "loop",
            lambda f: f.in_(["a", "b", "c"]).steps(inner),
            value="item",
        )
        d = _to_dict(sb)
        assert d == [
            {
                "loop": {
                    "for": {
                        "value": "item",
                        "in": ["a", "b", "c"],
                        "steps": [
                            {"log": {"call": "sys.log", "args": {"text": "${item}"}}}
                        ],
                    }
                }
            }
        ]


class TestForSubBuilder:
    """For sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().raw(
            "loop",
            For("item").in_(["a", "b", "c"]).steps(inner),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "loop": {
                    "for": {
                        "value": "item",
                        "in": ["a", "b", "c"],
                        "steps": [
                            {"log": {"call": "sys.log", "args": {"text": "${item}"}}}
                        ],
                    }
                }
            }
        ]

    def test_for_with_range(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().raw(
            "loop",
            For("item").range_([1, 10, 2]).steps(inner),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "loop": {
                    "for": {
                        "value": "item",
                        "range": [1, 10, 2],
                        "steps": [
                            {"log": {"call": "sys.log", "args": {"text": "${item}"}}}
                        ],
                    }
                }
            }
        ]

    def test_for_with_index(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().raw(
            "loop",
            For("item").in_(["a", "b"]).index("idx").steps(inner),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "loop": {
                    "for": {
                        "value": "item",
                        "index": "idx",
                        "in": ["a", "b"],
                        "steps": [
                            {"log": {"call": "sys.log", "args": {"text": "${item}"}}}
                        ],
                    }
                }
            }
        ]


class TestForFixture:
    """For step matches YAML fixture."""

    def test_for_loop_fixture(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().for_(
            "loop",
            value="item",
            in_=["a", "b", "c"],
            steps=inner,
        )
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert _to_dict(sb) == expected


# =============================================================================
# Parallel step
# =============================================================================


class TestParallelKwargs:
    """Parallel step via kwargs."""

    def test_parallel_branches(self):
        b1 = StepBuilder().call("b1_step", func="sys.log", args={"text": "branch1"})
        b2 = StepBuilder().call("b2_step", func="sys.log", args={"text": "branch2"})
        sb = StepBuilder().parallel(
            "parallel_work",
            branches={"branch1": b1, "branch2": b2},
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert d == expected


class TestParallelLambda:
    """Parallel step via lambda configurator."""

    def test_lambda_parallel(self):
        b1 = StepBuilder().call("b1_step", func="sys.log", args={"text": "branch1"})
        b2 = StepBuilder().call("b2_step", func="sys.log", args={"text": "branch2"})
        sb = StepBuilder().parallel(
            "parallel_work",
            lambda p: p.branch("branch1", b1).branch("branch2", b2),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert d == expected

    def test_lambda_parallel_with_shared(self):
        b1 = StepBuilder().assign("b1_step", result=1)
        b2 = StepBuilder().assign("b2_step", result=2)
        sb = StepBuilder().parallel(
            "work",
            lambda p: (p.branch("b1", b1).branch("b2", b2).shared(["result"])),
        )
        d = _to_dict(sb)
        assert d[0]["work"]["parallel"]["shared"] == ["result"]


class TestParallelSubBuilder:
    """Parallel sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        b1 = StepBuilder().call("b1_step", func="sys.log", args={"text": "branch1"})
        b2 = StepBuilder().call("b2_step", func="sys.log", args={"text": "branch2"})
        sb = StepBuilder().raw(
            "parallel_work",
            Parallel().branch("branch1", b1).branch("branch2", b2),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert d == expected


# =============================================================================
# Try step
# =============================================================================


class TestTryKwargs:
    """Try step via kwargs."""

    def test_try_call_with_retry_and_except(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raise_("handle", value=expr("e"))
        sb = StepBuilder().try_(
            "try_call",
            body=body,
            retry={
                "predicate": expr("e.code == 429"),
                "max_retries": 3,
                "backoff": {
                    "initial_delay": 1,
                    "max_delay": 30,
                    "multiplier": 2,
                },
            },
            except_={"as_": "e", "steps": except_steps},
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected


class TestTryLambda:
    """Try step via lambda configurator."""

    def test_lambda_try(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raise_("handle", value=expr("e"))
        sb = StepBuilder().try_(
            "try_call",
            lambda t: (
                t.body(body)
                .retry(
                    predicate=expr("e.code == 429"),
                    max_retries=3,
                    backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
                )
                .except_(as_="e", steps=except_steps)
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected


class TestTrySubBuilder:
    """Try sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raise_("handle", value=expr("e"))
        sb = StepBuilder().raw(
            "try_call",
            Try_(body)
            .retry(
                predicate=expr("e.code == 429"),
                max_retries=3,
                backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
            )
            .except_(as_="e", steps=except_steps),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected


# =============================================================================
# Nested steps
# =============================================================================


class TestNestedStepsKwargs:
    """Nested steps via kwargs."""

    def test_nested_steps(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .nested_steps("group", body=inner, next="done")
            .return_("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected


class TestNestedStepsLambda:
    """Nested steps via lambda configurator."""

    def test_lambda_nested_steps(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .nested_steps("group", lambda s: s.body(inner).next("done"))
            .return_("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected


class TestNestedStepsSubBuilder:
    """Nested steps sub-builder used directly via .raw()."""

    def test_direct_sub_builder(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .raw("group", Steps(inner).next("done"))
            .return_("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected


# =============================================================================
# Sub-builder .apply() tests
# =============================================================================


class TestAssignApply:
    """Assign sub-builder .apply() merges items."""

    def test_apply_assign_builder(self):
        common = Assign().set("content_type", "application/json")
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("url", "https://api.example.com").apply(common),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "init": {
                    "assign": [
                        {"url": "https://api.example.com"},
                        {"content_type": "application/json"},
                    ]
                }
            }
        ]

    def test_apply_callable_returns_builder(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).apply(lambda: Assign().set("debug", True)),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"debug": True}]}}]

    def test_apply_callable_returns_none(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).apply(lambda: None),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}]}}]


class TestCallApply:
    """Call sub-builder .apply() overwrites fields."""

    def test_apply_overwrites_args(self):
        auth = Call("").args(authorization="Bearer token123")
        sb = StepBuilder().call(
            "fetch",
            lambda c: c.func("http.get").args(url="https://example.com").apply(auth),
        )
        d = _to_dict(sb)
        # After apply, args should be overwritten with the auth args
        assert d[0]["fetch"]["call"] == "http.get"
        assert d[0]["fetch"]["args"] == {"authorization": "Bearer token123"}

    def test_apply_only_overwrites_set_fields(self):
        """Apply a Call that only sets result — func and args should remain."""
        partial = Call("").result("response")
        sb = StepBuilder().call(
            "fetch",
            lambda c: c.func("http.get").args(url="https://example.com").apply(partial),
        )
        d = _to_dict(sb)
        assert d[0]["fetch"]["call"] == "http.get"
        assert d[0]["fetch"]["args"] == {"url": "https://example.com"}
        assert d[0]["fetch"]["result"] == "response"


class TestSwitchApply:
    """Switch sub-builder .apply() appends conditions."""

    def test_apply_appends_conditions(self):
        fallback = Switch().condition(True, next="default")
        sb = StepBuilder().switch(
            "check",
            lambda s: (s.condition(expr("x > 0"), next="positive").apply(fallback)),
        )
        d = _to_dict(sb)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "next": "positive"},
                        {"condition": True, "next": "default"},
                    ]
                }
            }
        ]


class TestTryApply:
    """Try sub-builder .apply() overwrites retry/except."""

    def test_apply_retry_config(self):
        """Reusable retry config applied to a Try_ builder."""
        body = StepBuilder().call("call", func="http.get", args={"url": "..."})

        def add_retry(t):
            return t.retry(
                predicate=expr("e.code == 429"),
                max_retries=3,
                backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
            )

        sb = StepBuilder().try_(
            "safe",
            lambda t: add_retry(t.body(body)),
        )
        d = _to_dict(sb)
        assert d[0]["safe"]["retry"]["max_retries"] == 3


class TestParallelApply:
    """Parallel sub-builder .apply() appends branches."""

    def test_apply_appends_branches(self):
        extra = Parallel().branch(
            "branch3",
            StepBuilder().call("b3_step", func="sys.log", args={"text": "branch3"}),
        )
        b1 = StepBuilder().call("b1_step", func="sys.log", args={"text": "branch1"})
        b2 = StepBuilder().call("b2_step", func="sys.log", args={"text": "branch2"})
        sb = StepBuilder().parallel(
            "work",
            lambda p: p.branch("branch1", b1).branch("branch2", b2).apply(extra),
        )
        d = _to_dict(sb)
        branches = d[0]["work"]["parallel"]["branches"]
        assert len(branches) == 3
        assert "branch3" in branches[2]


# =============================================================================
# StepBuilder.apply() tests
# =============================================================================


class TestStepBuilderApply:
    """StepBuilder.apply() merges step sequences."""

    def test_apply_step_builder(self):
        setup = StepBuilder().assign("init", x=0)
        main = StepBuilder().apply(setup).return_("done", value=expr("x"))
        d = _to_dict(main)
        assert d == [
            {"init": {"assign": [{"x": 0}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_apply_callable_returns_builder(self):
        setup = StepBuilder().assign("init", x=0)
        main = StepBuilder().apply(lambda: setup).return_("done", value=expr("x"))
        d = _to_dict(main)
        assert d == [
            {"init": {"assign": [{"x": 0}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_apply_callable_returns_none(self):
        main = StepBuilder().apply(lambda: None).return_("done", value="ok")
        d = _to_dict(main)
        assert d == [{"done": {"return": "ok"}}]

    def test_apply_multiple_builders(self):
        setup = StepBuilder().assign("s1", x=1)
        middle = StepBuilder().assign("s2", y=2)
        main = (
            StepBuilder()
            .apply(setup)
            .apply(middle)
            .return_("done", value=expr("x + y"))
        )
        d = _to_dict(main)
        assert len(d) == 3
        assert d[0] == {"s1": {"assign": [{"x": 1}]}}
        assert d[1] == {"s2": {"assign": [{"y": 2}]}}

    def test_apply_enables_composition(self):
        """Compose reusable step sequences into workflows."""

        def logging_steps(message: str) -> StepBuilder:
            return StepBuilder().call("log", func="sys.log", args={"text": message})

        main = (
            StepBuilder()
            .assign("init", status="starting")
            .apply(logging_steps("workflow started"))
            .return_("done", value="ok")
        )
        d = _to_dict(main)
        assert len(d) == 3
        assert d[1] == {
            "log": {"call": "sys.log", "args": {"text": "workflow started"}}
        }


# =============================================================================
# Mixed construction & chaining
# =============================================================================


class TestMixedConstruction:
    """Test mixing all forms in a single StepBuilder chain."""

    def test_mixed_forms(self):
        sb = (
            StepBuilder()
            .assign("s1", x=10)  # kwargs
            .call("s2", lambda c: c.func("sys.log").args(text=expr("x")))  # lambda
            .raw("s3", ReturnStep(return_=expr("x")))  # model passthrough
        )
        d = _to_dict(sb)
        assert d[0] == {"s1": {"assign": [{"x": 10}]}}
        assert d[1] == {"s2": {"call": "sys.log", "args": {"text": "${x}"}}}
        assert d[2] == {"s3": {"return": "${x}"}}


class TestStepBuilderBuild:
    """Test StepBuilder.build() returns a list of Step objects."""

    def test_build_returns_list(self):
        sb = StepBuilder().assign("s1", x=1).return_("s2", value="ok")
        steps = sb.build()
        assert isinstance(steps, list)
        assert len(steps) == 2

    def test_build_empty(self):
        sb = StepBuilder()
        steps = sb.build()
        assert steps == []


# =============================================================================
# Validation integration
# =============================================================================


class TestStepBuilderValidation:
    """Built workflows pass the full validation pipeline."""

    def test_simple_assign_validates(self):
        sb = (
            StepBuilder()
            .assign("init", x=10, y=20)
            .return_("done", value=expr("x + y"))
        )
        w = WorkflowBuilder().workflow("main", sb).build()
        result = analyze_workflow(w)
        assert result.is_valid

    def test_subworkflows_validate(self):
        main = (
            StepBuilder()
            .call(
                "call_helper",
                func="helper",
                args={"input": "test"},
                result="res",
            )
            .return_("done", value=expr("res"))
        )
        helper = (
            StepBuilder()
            .call("log", func="sys.log", args={"text": expr("input")})
            .return_("done", value="ok")
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


class TestStepBuilderErrors:
    """Error handling for StepBuilder."""

    def test_assign_no_items_raises(self):
        """Assign with no kwargs and no lambda should raise."""
        with pytest.raises(ValueError):
            StepBuilder().assign("bad")

    def test_call_no_func_raises(self):
        """Call with no func kwarg and no lambda should raise."""
        with pytest.raises(ValueError):
            StepBuilder().call("bad")

    def test_return_no_value_raises(self):
        """Return with no value kwarg and no lambda should raise."""
        with pytest.raises(ValueError):
            StepBuilder().return_("bad")

    def test_raise_no_value_raises(self):
        """Raise with no value kwarg and no lambda should raise."""
        with pytest.raises(ValueError):
            StepBuilder().raise_("bad")


class TestSubBuilderTypeErrors:
    """Sub-builder .apply() rejects wrong types."""

    def test_assign_apply_rejects_call(self):
        """Cannot apply a Call builder onto an Assign builder."""
        with pytest.raises(TypeError):
            Assign().set("x", 1).apply(Call("sys.log"))

    def test_call_apply_rejects_assign(self):
        """Cannot apply an Assign builder onto a Call builder."""
        with pytest.raises(TypeError):
            Call("http.get").apply(Assign().set("x", 1))
