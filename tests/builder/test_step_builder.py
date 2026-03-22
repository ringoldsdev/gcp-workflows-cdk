"""Tests for StepBuilder and step sub-builder classes.

Consolidated from the original test_step_builder.py:
- Merged per-type multi-class (Kwargs/Lambda/SubBuilder/Passthrough/Fixture)
  into one class per step type.
- Kept all meaningful tests, just restructured classes.

Each test builds steps, serializes to dict, and compares against expected output.
"""

import pytest
import yaml

from cloud_workflows import (
    StepBuilder,
    Workflow,
    Subworkflow,
    analyze_workflow,
    expr,
)
from cloud_workflows.steps import (
    Assign,
    Call,
    Returns,
    Raises,
    Switch,
    Loop,
    Parallel,
    DoTry,
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
    w = Workflow().apply(sb).build()
    assert isinstance(w, SimpleWorkflow)
    return w.to_dict()


# =============================================================================
# Assign step
# =============================================================================


class TestAssign:
    """Assign step: kwargs, lambda, sub-builder, model passthrough, and fixture."""

    # -- kwargs --

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

    # -- lambda --

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

    # -- model passthrough --

    def test_pydantic_model(self):
        sb = StepBuilder().raw("init", AssignStep(assign=[{"x": 10}, {"y": 20}]))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_dict_passthrough(self):
        sb = StepBuilder().raw("init", {"assign": [{"x": 10}, {"y": 20}]})
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    # -- sub-builder --

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("init", Assign().set("x", 10).set("y", 20))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    # -- fixture --

    def test_simple_assign_fixture(self):
        sb = (
            StepBuilder()
            .assign("init", x=10, y=20)
            .returns("done", value=expr("x + y"))
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


class TestCall:
    """Call step: kwargs, lambda, sub-builder, and model passthrough."""

    # -- kwargs --

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

    # -- lambda --

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

    # -- sub-builder --

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("log", Call("sys.log").args(text="hello"))
        d = _to_dict(sb)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]

    # -- model passthrough --

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


class TestReturn:
    """Return step: kwargs, lambda, sub-builder, and model passthrough."""

    def test_return_value(self):
        sb = StepBuilder().returns("done", value="ok")
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]

    def test_return_expr(self):
        sb = StepBuilder().returns("done", value=expr("x + y"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "${x + y}"}}]

    def test_lambda_return(self):
        sb = StepBuilder().returns("done", lambda r: r.value("ok"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("done", Returns(expr("x + y")))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "${x + y}"}}]

    def test_pydantic_model(self):
        sb = StepBuilder().raw("done", ReturnStep(return_="ok"))
        d = _to_dict(sb)
        assert d == [{"done": {"return": "ok"}}]


# =============================================================================
# Raise step
# =============================================================================


class TestRaise:
    """Raise step: kwargs, lambda, and sub-builder."""

    def test_raise_string(self):
        sb = StepBuilder().raises("fail", value="something went wrong")
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": "something went wrong"}}]

    def test_raise_dict(self):
        sb = StepBuilder().raises("fail", value={"code": 404, "message": "not found"})
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": {"code": 404, "message": "not found"}}}]

    def test_lambda_raise(self):
        sb = StepBuilder().raises("fail", lambda r: r.value(expr("e")))
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": "${e}"}}]

    def test_direct_sub_builder(self):
        sb = StepBuilder().raw("fail", Raises({"code": 404}))
        d = _to_dict(sb)
        assert d == [{"fail": {"raise": {"code": 404}}}]


# =============================================================================
# Switch step
# =============================================================================


class TestSwitch:
    """Switch step: kwargs, lambda, sub-builder, and fixture."""

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
            .returns("positive", value="positive")
            .returns("negative", value="negative")
        )
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert _to_dict(sb) == expected


# =============================================================================
# For step
# =============================================================================


class TestFor:
    """For step: kwargs, lambda, sub-builder (with range/index), and fixture."""

    def test_for_in(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().loop(
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

    def test_lambda_for(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().loop(
            "loop",
            lambda f: f.items(["a", "b", "c"]).steps(inner),
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

    def test_direct_sub_builder(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().raw(
            "loop",
            Loop("item").items(["a", "b", "c"]).steps(inner),
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
            Loop("item").range([1, 10, 2]).steps(inner),
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
            Loop("item").items(["a", "b"]).index("idx").steps(inner),
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

    def test_for_loop_fixture(self):
        inner = StepBuilder().call("log", func="sys.log", args={"text": expr("item")})
        sb = StepBuilder().loop(
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


class TestParallel:
    """Parallel step: kwargs, lambda, and sub-builder."""

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


class TestTry:
    """Try step: kwargs, lambda, and sub-builder."""

    def test_try_call_with_retry_and_except(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raises("handle", value=expr("e"))
        sb = StepBuilder().do_try(
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

    def test_lambda_try(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raises("handle", value=expr("e"))
        sb = StepBuilder().do_try(
            "try_call",
            lambda t: (
                t.body(body)
                .retry(
                    predicate=expr("e.code == 429"),
                    max_retries=3,
                    backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
                )
                .exception(error="e", steps=except_steps)
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected

    def test_direct_sub_builder(self):
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        except_steps = StepBuilder().raises("handle", value=expr("e"))
        sb = StepBuilder().raw(
            "try_call",
            DoTry(body)
            .retry(
                predicate=expr("e.code == 429"),
                max_retries=3,
                backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
            )
            .exception(error="e", steps=except_steps),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected


# =============================================================================
# Nested steps
# =============================================================================


class TestNestedSteps:
    """Nested steps: kwargs, lambda, and sub-builder."""

    def test_nested_steps(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .nested_steps("group", body=inner, next="done")
            .returns("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected

    def test_lambda_nested_steps(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .nested_steps("group", lambda s: s.body(inner).next("done"))
            .returns("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected

    def test_direct_sub_builder(self):
        inner = (
            StepBuilder()
            .call("step_a", func="sys.log", args={"text": "a"})
            .call("step_b", func="sys.log", args={"text": "b"})
        )
        sb = (
            StepBuilder()
            .raw("group", Steps(inner).next("done"))
            .returns("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected


# =============================================================================
# Sub-builder .apply() tests
# =============================================================================


class TestApply:
    """Sub-builder .apply() for all step types."""

    # -- Assign apply --

    def test_assign_apply_builder(self):
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

    def test_assign_apply_callable_returns_builder(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).apply(lambda: Assign().set("debug", True)),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}, {"debug": True}]}}]

    def test_assign_apply_callable_returns_none(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("x", 10).apply(lambda: None),
        )
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 10}]}}]

    # -- Call apply --

    def test_call_apply_overwrites_args(self):
        auth = Call("").args(authorization="Bearer token123")
        sb = StepBuilder().call(
            "fetch",
            lambda c: c.func("http.get").args(url="https://example.com").apply(auth),
        )
        d = _to_dict(sb)
        assert d[0]["fetch"]["call"] == "http.get"
        assert d[0]["fetch"]["args"] == {"authorization": "Bearer token123"}

    def test_call_apply_only_overwrites_set_fields(self):
        """Apply a Call that only sets result -- func and args should remain."""
        partial = Call("").result("response")
        sb = StepBuilder().call(
            "fetch",
            lambda c: c.func("http.get").args(url="https://example.com").apply(partial),
        )
        d = _to_dict(sb)
        assert d[0]["fetch"]["call"] == "http.get"
        assert d[0]["fetch"]["args"] == {"url": "https://example.com"}
        assert d[0]["fetch"]["result"] == "response"

    # -- Switch apply --

    def test_switch_apply_appends_conditions(self):
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

    # -- Try apply --

    def test_try_apply_retry_config(self):
        """Reusable retry config applied to a DoTry builder."""
        body = StepBuilder().call("call", func="http.get", args={"url": "..."})

        def add_retry(t):
            return t.retry(
                predicate=expr("e.code == 429"),
                max_retries=3,
                backoff={"initial_delay": 1, "max_delay": 30, "multiplier": 2},
            )

        sb = StepBuilder().do_try(
            "safe",
            lambda t: add_retry(t.body(body)),
        )
        d = _to_dict(sb)
        assert d[0]["safe"]["retry"]["max_retries"] == 3

    # -- Parallel apply --

    def test_parallel_apply_appends_branches(self):
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
        main = StepBuilder().apply(setup).returns("done", value=expr("x"))
        d = _to_dict(main)
        assert d == [
            {"init": {"assign": [{"x": 0}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_apply_callable_returns_builder(self):
        setup = StepBuilder().assign("init", x=0)
        main = StepBuilder().apply(lambda: setup).returns("done", value=expr("x"))
        d = _to_dict(main)
        assert d == [
            {"init": {"assign": [{"x": 0}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_apply_callable_returns_none(self):
        main = StepBuilder().apply(lambda: None).returns("done", value="ok")
        d = _to_dict(main)
        assert d == [{"done": {"return": "ok"}}]

    def test_apply_multiple_builders(self):
        setup = StepBuilder().assign("s1", x=1)
        middle = StepBuilder().assign("s2", y=2)
        main = (
            StepBuilder()
            .apply(setup)
            .apply(middle)
            .returns("done", value=expr("x + y"))
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
            .returns("done", value="ok")
        )
        d = _to_dict(main)
        assert len(d) == 3
        assert d[1] == {
            "log": {"call": "sys.log", "args": {"text": "workflow started"}}
        }


# =============================================================================
# Dot-path unnesting
# =============================================================================


class TestDotPathUnnesting:
    """Assign.set() and StepBuilder.assign() kwargs unnest dot-separated keys."""

    # -- via Assign.set() --

    def test_set_dotpath_simple(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: a.set("a.b.c", 1).set("x", 10),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_assign.yaml"))
        assert d == expected

    def test_set_dotpath_deep(self):
        sb = StepBuilder().assign(
            "init",
            lambda a: (
                a.set("config.http.timeout", 30)
                .set("config.http.retries", 3)
                .set("simple", True)
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_deep.yaml"))
        assert d == expected

    def test_set_no_dot_unchanged(self):
        """Keys without dots are not affected."""
        sb = StepBuilder().assign("init", lambda a: a.set("x", 1))
        d = _to_dict(sb)
        assert d == [{"init": {"assign": [{"x": 1}]}}]

    # -- via StepBuilder.assign() kwargs --

    def test_kwargs_dotpath(self):
        """StepBuilder.assign() kwargs pass through Assign.set() which unnests."""
        sb = StepBuilder().assign("init", **{"a.b.c": 1, "x": 10})
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_assign.yaml"))
        assert d == expected

    def test_kwargs_dotpath_deep(self):
        sb = StepBuilder().assign(
            "init",
            **{
                "config.http.timeout": 30,
                "config.http.retries": 3,
                "simple": True,
            },
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_deep.yaml"))
        assert d == expected

    # -- direct sub-builder --

    def test_direct_sub_builder_dotpath(self):
        sb = StepBuilder().raw(
            "init",
            Assign().set("a.b.c", 1).set("x", 10),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_assign.yaml"))
        assert d == expected


# =============================================================================
# Lambda inner StepBuilder on sub-builders
# =============================================================================


class TestLambdaInnerStepBuilder:
    """Sub-builders accept lambdas that receive a StepBuilder for inner steps."""

    # -- Loop.steps() --

    def test_for_steps_lambda(self):
        """Loop.steps() accepts a lambda that receives a StepBuilder."""
        sb = StepBuilder().loop(
            "loop",
            lambda f: f.items(["a", "b", "c"]).steps(
                lambda s: s.call("log", func="sys.log", args={"text": expr("item")})
            ),
            value="item",
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "for_lambda_inner.yaml"))
        assert d == expected

    def test_for_direct_sub_builder_lambda(self):
        """Loop() sub-builder used via .raw() with lambda steps."""
        sb = StepBuilder().raw(
            "loop",
            Loop("item")
            .items(["a", "b", "c"])
            .steps(
                lambda s: s.call("log", func="sys.log", args={"text": expr("item")})
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "for_lambda_inner.yaml"))
        assert d == expected

    # -- Parallel.branch() --

    def test_parallel_branch_lambda(self):
        """Parallel.branch() accepts a lambda that receives a StepBuilder."""
        sb = StepBuilder().parallel(
            "parallel_work",
            lambda p: p.branch(
                "branch1",
                lambda s: s.call("b1_step", func="sys.log", args={"text": "branch1"}),
            ).branch(
                "branch2",
                lambda s: s.call("b2_step", func="sys.log", args={"text": "branch2"}),
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_lambda_inner.yaml"))
        assert d == expected

    def test_parallel_direct_sub_builder_lambda(self):
        """Parallel() sub-builder used via .raw() with lambda steps."""
        sb = StepBuilder().raw(
            "parallel_work",
            Parallel()
            .branch(
                "branch1",
                lambda s: s.call("b1_step", func="sys.log", args={"text": "branch1"}),
            )
            .branch(
                "branch2",
                lambda s: s.call("b2_step", func="sys.log", args={"text": "branch2"}),
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_lambda_inner.yaml"))
        assert d == expected

    # -- DoTry.body() --

    def test_try_body_lambda(self):
        """DoTry.body() accepts a lambda that receives a StepBuilder."""
        sb = StepBuilder().do_try(
            "try_call",
            lambda t: t.body(
                lambda s: s.call(
                    "call",
                    func="http.get",
                    args={"url": "https://example.com"},
                    result="response",
                )
            ).except_(
                as_="e",
                steps=StepBuilder().raises("handle", value=expr("e")),
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_lambda_inner.yaml"))
        assert d == expected

    def test_try_direct_sub_builder_lambda_body(self):
        """DoTry() sub-builder used via .raw() with lambda body."""
        sb = StepBuilder().raw(
            "try_call",
            DoTry(
                lambda s: s.call(
                    "call",
                    func="http.get",
                    args={"url": "https://example.com"},
                    result="response",
                )
            ).exception(
                error="e",
                steps=StepBuilder().raises("handle", value=expr("e")),
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_lambda_inner.yaml"))
        assert d == expected

    # -- DoTry.exception(steps=lambda) --

    def test_try_except_steps_lambda(self):
        """DoTry.exception(steps=lambda) accepts a lambda for the except handler."""
        body = StepBuilder().call(
            "call",
            func="http.get",
            args={"url": "https://example.com"},
            result="response",
        )
        sb = StepBuilder().do_try(
            "try_call",
            lambda t: t.body(body).except_(
                as_="e",
                steps=lambda s: s.raises("handle", value=expr("e")),
            ),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "try_lambda_inner.yaml"))
        assert d == expected

    # -- Steps.body() --

    def test_steps_body_lambda(self):
        """Steps.body() accepts a lambda that receives a StepBuilder."""
        sb = (
            StepBuilder()
            .nested_steps(
                "group",
                lambda s: s.body(
                    lambda inner: inner.call(
                        "step_a", func="sys.log", args={"text": "a"}
                    ).call("step_b", func="sys.log", args={"text": "b"})
                ).next("done"),
            )
            .returns("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "steps_lambda_inner.yaml"))
        assert d == expected

    def test_steps_direct_sub_builder_lambda(self):
        """Steps() sub-builder used via .raw() with lambda body."""
        sb = (
            StepBuilder()
            .raw(
                "group",
                Steps(
                    lambda inner: inner.call(
                        "step_a", func="sys.log", args={"text": "a"}
                    ).call("step_b", func="sys.log", args={"text": "b"})
                ).next("done"),
            )
            .returns("done", value="ok")
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "steps_lambda_inner.yaml"))
        assert d == expected

    # -- Switch.condition(steps=lambda) --

    def test_switch_condition_steps_lambda(self):
        """Switch.condition(steps=lambda) accepts a lambda for inline steps."""
        sb = StepBuilder().switch(
            "check",
            lambda s: s.condition(
                expr("x > 0"),
                steps=lambda inner: inner.call(
                    "log_positive", func="sys.log", args={"text": "positive"}
                ),
            ).condition(True, next="fallback"),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "switch_lambda_inner.yaml"))
        assert d == expected

    def test_switch_direct_sub_builder_lambda_steps(self):
        """Switch() sub-builder used via .raw() with lambda steps in condition."""
        sb = StepBuilder().raw(
            "check",
            Switch()
            .condition(
                expr("x > 0"),
                steps=lambda inner: inner.call(
                    "log_positive", func="sys.log", args={"text": "positive"}
                ),
            )
            .condition(True, next="fallback"),
        )
        d = _to_dict(sb)
        expected = yaml.safe_load(load_fixture("cdk", "switch_lambda_inner.yaml"))
        assert d == expected


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

    def test_expr_in_dict(self):
        """expr() helper works when passed inside raw dict bodies."""
        w = (
            Workflow()
            .raw("init", {"assign": [{"x": 1}]})
            .raw("done", {"return": expr("x + 1")})
            .build()
        )
        assert w.to_dict() == [
            {"init": {"assign": [{"x": 1}]}},
            {"done": {"return": "${x + 1}"}},
        ]


class TestStepBuilderBuild:
    """Test StepBuilder.build() returns a list of Step objects."""

    def test_build_returns_list(self):
        sb = StepBuilder().assign("s1", x=1).returns("s2", value="ok")
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
        w = (
            Workflow()
            .assign("init", x=10, y=20)
            .returns("done", value=expr("x + y"))
            .build()
        )
        result = analyze_workflow(w)
        assert result.is_valid

    def test_subworkflows_validate(self):
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
        w = Workflow({"main": main, "helper": helper}).build()
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
            StepBuilder().returns("bad")

    def test_raise_no_value_raises(self):
        """Raise with no value kwarg and no lambda should raise."""
        with pytest.raises(ValueError):
            StepBuilder().raises("bad")

    def test_pydantic_validation_in_builder(self):
        """Pydantic validation runs eagerly at model construction time."""
        with pytest.raises(Exception):
            StepBuilder().raw("bad", AssignStep(assign=[]))


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
