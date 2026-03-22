"""Tests for step classes and Steps container.

Each test constructs steps using the new class-based API, serializes to
dict via Steps.build(), and compares against expected output or fixtures.
"""

import pytest
import yaml

from cloud_workflows import (
    Steps,
    Assign,
    Call,
    Return,
    Raise,
    Switch,
    Condition,
    For,
    Parallel,
    Try,
    NestedSteps,
    analyze_workflow,
    expr,
)
from cloud_workflows.models import (
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SimpleWorkflow,
)
from conftest import load_fixture


# =============================================================================
# Helper: build Steps into a SimpleWorkflow for comparison
# =============================================================================


def _to_dict(s: Steps) -> list:
    """Finalize Steps into a SimpleWorkflow and serialize to dict."""
    w = s._finalize()
    assert isinstance(w, SimpleWorkflow)
    return w.to_dict()


# =============================================================================
# Assign step
# =============================================================================


class TestAssign:
    """Assign step: kwargs, dict mapping, dotted paths, and fixture."""

    def test_simple_assign(self):
        s = Steps()
        s("init", Assign(x=10, y=20))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_assign_with_expr(self):
        s = Steps()
        s("init", Assign(x=10, y=expr("x + 1")))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": "${x + 1}"}]}}]

    def test_assign_with_dict_mapping(self):
        """Dict mapping supports complex keys like map["key"]."""
        s = Steps()
        s("init", Assign({"x": 10, 'map["key"]': "value"}))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {'map["key"]': "value"}]}}]

    def test_assign_dict_and_kwargs(self):
        """Dict and kwargs can be combined."""
        s = Steps()
        s("init", Assign({"x": 10}, y=20))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_assign_with_next(self):
        s = Steps()
        s("init", Assign(x=10, next="done"))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}], "next": "done"}}]

    def test_simple_assign_fixture(self):
        s = Steps()
        s("init", Assign(x=10, y=20))
        s("done", Return(expr("x + y")))
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        assert _to_dict(s) == expected

    def test_pydantic_model_passthrough(self):
        """Raw Pydantic models can still be used via Steps.build() approach."""
        # This tests that the model output format matches
        model = AssignStep(assign=[{"x": 10}, {"y": 20}])
        body = model.model_dump(by_alias=True, exclude_none=True)
        s = Steps()
        s("init", Assign(x=10, y=20))
        d = _to_dict(s)
        assert d == [{"init": body}]


# =============================================================================
# Call step
# =============================================================================


class TestCall:
    """Call step: basic, with result, with next."""

    def test_simple_call(self):
        s = Steps()
        s("log", Call("sys.log", args={"text": "hello"}))
        d = _to_dict(s)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]

    def test_call_with_result(self):
        s = Steps()
        s("fetch", Call("http.get", args={"url": "https://example.com"}, result="resp"))
        d = _to_dict(s)
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
        s = Steps()
        s("log", Call("sys.log", args={"text": "hello"}, next="done"))
        d = _to_dict(s)
        assert d == [
            {"log": {"call": "sys.log", "args": {"text": "hello"}, "next": "done"}}
        ]

    def test_call_matches_model(self):
        model = CallStep(call="sys.log", args={"text": "hello"})
        body = model.model_dump(by_alias=True, exclude_none=True)
        s = Steps()
        s("log", Call("sys.log", args={"text": "hello"}))
        d = _to_dict(s)
        assert d == [{"log": body}]


# =============================================================================
# Return step
# =============================================================================


class TestReturn:
    """Return step: string, expression, None."""

    def test_return_value(self):
        s = Steps()
        s("done", Return("ok"))
        d = _to_dict(s)
        assert d == [{"done": {"return": "ok"}}]

    def test_return_expr(self):
        s = Steps()
        s("done", Return(expr("x + y")))
        d = _to_dict(s)
        assert d == [{"done": {"return": "${x + y}"}}]

    def test_return_matches_model(self):
        model = ReturnStep(return_="ok")
        body = model.model_dump(by_alias=True, exclude_none=True)
        s = Steps()
        s("done", Return("ok"))
        d = _to_dict(s)
        assert d == [{"done": body}]


# =============================================================================
# Raise step
# =============================================================================


class TestRaise:
    """Raise step: string, dict, expression."""

    def test_raise_string(self):
        s = Steps()
        s("fail", Raise("something went wrong"))
        d = _to_dict(s)
        assert d == [{"fail": {"raise": "something went wrong"}}]

    def test_raise_dict(self):
        s = Steps()
        s("fail", Raise({"code": 404, "message": "not found"}))
        d = _to_dict(s)
        assert d == [{"fail": {"raise": {"code": 404, "message": "not found"}}}]

    def test_raise_expr(self):
        s = Steps()
        s("fail", Raise(expr("e")))
        d = _to_dict(s)
        assert d == [{"fail": {"raise": "${e}"}}]


# =============================================================================
# Switch step
# =============================================================================


class TestSwitch:
    """Switch step: conditions, next, inline steps, fixture."""

    def test_switch_conditions(self):
        s = Steps()
        s(
            "check",
            Switch(
                [
                    Condition(expr("x > 0"), next="positive"),
                    Condition(True, next="negative"),
                ]
            ),
        )
        d = _to_dict(s)
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

    def test_switch_with_next(self):
        s = Steps()
        s(
            "check",
            Switch(
                [Condition(expr("x > 0"), next="positive")],
                next="fallback",
            ),
        )
        d = _to_dict(s)
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

    def test_switch_fixture(self):
        s = Steps()
        s("init", Assign(x=10))
        s(
            "check",
            Switch(
                [
                    Condition(expr("x > 0"), next="positive"),
                    Condition(True, next="negative"),
                ]
            ),
        )
        s("positive", Return("positive"))
        s("negative", Return("negative"))
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert _to_dict(s) == expected

    def test_switch_with_inline_steps(self):
        inner = Steps()
        inner("log_positive", Call("sys.log", args={"text": "positive"}))

        s = Steps()
        s(
            "check",
            Switch(
                [
                    Condition(expr("x > 0"), steps=inner),
                    Condition(True, next="fallback"),
                ]
            ),
        )
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "switch_lambda_inner.yaml"))
        assert d == expected


# =============================================================================
# For step
# =============================================================================


class TestFor:
    """For step: items, range, index, fixture."""

    def test_for_in(self):
        inner = Steps()
        inner("log", Call("sys.log", args={"text": expr("item")}))

        s = Steps()
        s("loop", For(value="item", items=["a", "b", "c"], steps=inner))
        d = _to_dict(s)
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
        inner = Steps()
        inner("log", Call("sys.log", args={"text": expr("item")}))

        s = Steps()
        s("loop", For(value="item", range=[1, 10, 2], steps=inner))
        d = _to_dict(s)
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
        inner = Steps()
        inner("log", Call("sys.log", args={"text": expr("item")}))

        s = Steps()
        s("loop", For(value="item", items=["a", "b"], index="idx", steps=inner))
        d = _to_dict(s)
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
        inner = Steps()
        inner("log", Call("sys.log", args={"text": expr("item")}))

        s = Steps()
        s("loop", For(value="item", items=["a", "b", "c"], steps=inner))
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert _to_dict(s) == expected

    def test_for_lambda_inner_fixture(self):
        """Match the for_lambda_inner.yaml fixture (same as for_loop.yaml)."""
        inner = Steps()
        inner("log", Call("sys.log", args={"text": expr("item")}))

        s = Steps()
        s("loop", For(value="item", items=["a", "b", "c"], steps=inner))
        expected = yaml.safe_load(load_fixture("cdk", "for_lambda_inner.yaml"))
        assert _to_dict(s) == expected


# =============================================================================
# Parallel step
# =============================================================================


class TestParallel:
    """Parallel step: branches, shared, fixture."""

    def test_parallel_branches(self):
        b1 = Steps()
        b1("b1_step", Call("sys.log", args={"text": "branch1"}))
        b2 = Steps()
        b2("b2_step", Call("sys.log", args={"text": "branch2"}))

        s = Steps()
        s("parallel_work", Parallel(branches={"branch1": b1, "branch2": b2}))
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "parallel_branches.yaml"))
        assert d == expected

    def test_parallel_with_shared(self):
        b1 = Steps()
        b1("b1_step", Assign(result=1))
        b2 = Steps()
        b2("b2_step", Assign(result=2))

        s = Steps()
        s(
            "work",
            Parallel(branches={"b1": b1, "b2": b2}, shared=["result"]),
        )
        d = _to_dict(s)
        assert d[0]["work"]["parallel"]["shared"] == ["result"]

    def test_parallel_fixture(self):
        b1 = Steps()
        b1("b1_step", Call("sys.log", args={"text": "branch1"}))
        b2 = Steps()
        b2("b2_step", Call("sys.log", args={"text": "branch2"}))

        s = Steps()
        s("parallel_work", Parallel(branches={"branch1": b1, "branch2": b2}))
        expected = yaml.safe_load(load_fixture("cdk", "parallel_lambda_inner.yaml"))
        assert _to_dict(s) == expected


# =============================================================================
# Try step
# =============================================================================


class TestTry:
    """Try step: call body auto-detection, retry, except, fixture."""

    def test_try_call_with_retry_and_except(self):
        body = Steps()
        body(
            "call",
            Call(
                "http.get",
                args={"url": "https://example.com"},
                result="response",
            ),
        )
        except_steps = Steps()
        except_steps("handle", Raise(expr("e")))

        s = Steps()
        s(
            "try_call",
            Try(
                steps=body,
                retry={
                    "predicate": expr("e.code == 429"),
                    "max_retries": 3,
                    "backoff": {
                        "initial_delay": 1,
                        "max_delay": 30,
                        "multiplier": 2,
                    },
                },
                error_steps=except_steps,
            ),
        )
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "try_except_retry.yaml"))
        assert d == expected

    def test_try_lambda_inner_fixture(self):
        """Try with single call body and except handler."""
        body = Steps()
        body(
            "call",
            Call(
                "http.get",
                args={"url": "https://example.com"},
                result="response",
            ),
        )
        except_steps = Steps()
        except_steps("handle", Raise(expr("e")))

        s = Steps()
        s(
            "try_call",
            Try(steps=body, error_steps=except_steps),
        )
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "try_lambda_inner.yaml"))
        assert d == expected


# =============================================================================
# Nested steps
# =============================================================================


class TestNestedSteps:
    """Nested steps: grouping and fixture."""

    def test_nested_steps(self):
        inner = Steps()
        inner("step_a", Call("sys.log", args={"text": "a"}))
        inner("step_b", Call("sys.log", args={"text": "b"}))

        s = Steps()
        s("group", NestedSteps(steps=inner, next="done"))
        s("done", Return("ok"))
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "nested_steps.yaml"))
        assert d == expected

    def test_nested_steps_lambda_inner_fixture(self):
        inner = Steps()
        inner("step_a", Call("sys.log", args={"text": "a"}))
        inner("step_b", Call("sys.log", args={"text": "b"}))

        s = Steps()
        s("group", NestedSteps(steps=inner, next="done"))
        s("done", Return("ok"))
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "steps_lambda_inner.yaml"))
        assert d == expected


# =============================================================================
# Steps container composition
# =============================================================================


class TestStepsComposition:
    """Steps composition via __call__(other_steps)."""

    def test_merge_steps(self):
        setup = Steps()
        setup("init", Assign(x=0))

        main = Steps()
        main(setup)
        main("done", Return(expr("x")))
        d = _to_dict(main)
        assert d == [
            {"init": {"assign": [{"x": 0}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_merge_multiple_steps(self):
        s1 = Steps()
        s1("s1", Assign(x=1))

        s2 = Steps()
        s2("s2", Assign(y=2))

        main = Steps()
        main(s1)
        main(s2)
        main("done", Return(expr("x + y")))
        d = _to_dict(main)
        assert len(d) == 3
        assert d[0] == {"s1": {"assign": [{"x": 1}]}}
        assert d[1] == {"s2": {"assign": [{"y": 2}]}}

    def test_composition_enables_reuse(self):
        """Compose reusable step sequences into workflows."""

        def logging_steps(message: str) -> Steps:
            s = Steps()
            s("log", Call("sys.log", args={"text": message}))
            return s

        main = Steps()
        main("init", Assign(status="starting"))
        main(logging_steps("workflow started"))
        main("done", Return("ok"))
        d = _to_dict(main)
        assert len(d) == 3
        assert d[1] == {
            "log": {"call": "sys.log", "args": {"text": "workflow started"}}
        }


# =============================================================================
# Dot-path unnesting
# =============================================================================


class TestDotPathUnnesting:
    """Assign with dot-separated keys unnest into nested dicts."""

    def test_dotpath_simple(self):
        s = Steps()
        s("init", Assign({"a.b.c": 1}, x=10))
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_assign.yaml"))
        assert d == expected

    def test_dotpath_deep(self):
        s = Steps()
        s(
            "init",
            Assign(
                {
                    "config.http.timeout": 30,
                    "config.http.retries": 3,
                },
                simple=True,
            ),
        )
        d = _to_dict(s)
        expected = yaml.safe_load(load_fixture("cdk", "dotpath_deep.yaml"))
        assert d == expected

    def test_no_dot_unchanged(self):
        s = Steps()
        s("init", Assign(x=1))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 1}]}}]


# =============================================================================
# Mixed construction
# =============================================================================


class TestMixedConstruction:
    """Mixing different step types in a single Steps container."""

    def test_mixed_types(self):
        s = Steps()
        s("s1", Assign(x=10))
        s("s2", Call("sys.log", args={"text": expr("x")}))
        s("s3", Return(expr("x")))
        d = _to_dict(s)
        assert d[0] == {"s1": {"assign": [{"x": 10}]}}
        assert d[1] == {"s2": {"call": "sys.log", "args": {"text": "${x}"}}}
        assert d[2] == {"s3": {"return": "${x}"}}


class TestStepsBuild:
    """Steps.build() returns a list of dicts."""

    def test_build_returns_list(self):
        s = Steps()
        s("s1", Assign(x=1))
        s("s2", Return("ok"))
        result = s.build()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_build_empty(self):
        s = Steps()
        result = s.build()
        assert result == []


# =============================================================================
# Validation integration
# =============================================================================


class TestValidation:
    """Built workflows pass the full validation pipeline."""

    def test_simple_assign_validates(self):
        s = Steps()
        s("init", Assign(x=10, y=20))
        s("done", Return(expr("x + y")))
        w = s._finalize()
        result = analyze_workflow(w)
        assert result.is_valid

    def test_subworkflows_validate(self):
        from cloud_workflows.builder import build as build_fn

        main = Steps()
        main(
            "call_helper",
            Call("helper", args={"input": "test"}, result="res"),
        )
        main("done", Return(expr("res")))

        helper = Steps(params=["input"])
        helper("log", Call("sys.log", args={"text": expr("input")}))
        helper("done", Return("ok"))

        w = build_fn.__wrapped__ if hasattr(build_fn, "__wrapped__") else None

        # Build multi-workflow via dict
        from cloud_workflows.builder import _finalize

        workflow = _finalize({"main": main, "helper": helper})
        result = analyze_workflow(workflow)
        assert result.is_valid


# =============================================================================
# Error cases
# =============================================================================


class TestErrors:
    """Error handling for step classes and Steps container."""

    def test_assign_no_items_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            Assign()

    def test_call_no_func_raises(self):
        with pytest.raises(ValueError, match="function name"):
            Call("")

    def test_return_no_value_raises(self):
        with pytest.raises(ValueError, match="requires a value"):
            Return()

    def test_raise_no_value_raises(self):
        with pytest.raises(ValueError, match="requires a value"):
            Raise()

    def test_switch_no_conditions_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            Switch([])

    def test_for_no_collection_raises(self):
        s = Steps()
        with pytest.raises(ValueError, match="items or range"):
            For(value="item", steps=s)

    def test_parallel_no_branches_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            Parallel(branches={})

    def test_steps_missing_step_type(self):
        """Calling Steps with step_id but no StepType raises."""
        s = Steps()
        with pytest.raises(TypeError, match="Missing step type"):
            s("bad")

    def test_steps_wrong_type(self):
        """Calling Steps with non-StepType raises."""
        s = Steps()
        with pytest.raises(TypeError, match="StepType"):
            s("bad", "not a step type")  # type: ignore[arg-type]

    def test_steps_merge_with_extra_arg(self):
        """Merging Steps with extra arg raises."""
        s1 = Steps()
        s2 = Steps()
        with pytest.raises(TypeError, match="no second argument"):
            s1(s2, Assign(x=1))  # type: ignore[call-overload]

    def test_finalize_empty_raises(self):
        s = Steps()
        with pytest.raises(ValueError, match="No steps"):
            s._finalize()

    def test_pydantic_validation_in_step(self):
        """Pydantic validation runs eagerly at model construction time."""
        with pytest.raises(Exception):
            AssignStep(assign=[])
