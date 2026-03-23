"""Tests for Steps alias convenience methods.

Each test constructs steps using the alias API (.assign(), .call(), etc.),
serializes via Steps.build(), and compares against expected output or fixtures.
Verifies that alias methods produce identical output to .step() with explicit
StepType instances.
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
    Retry,
    Backoff,
    expr,
)
from cloud_workflows.models import SimpleWorkflow
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
# .assign()
# =============================================================================


class TestAssignAlias:
    """Tests for Steps.assign() alias method."""

    def test_simple_kwargs(self):
        s = Steps().assign("init", x=10, y=20)
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_with_mapping_dict(self):
        s = Steps().assign("init", {"x": 10, 'map["key"]': "value"})
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {'map["key"]': "value"}]}}]

    def test_mapping_and_kwargs(self):
        s = Steps().assign("init", {"x": 10}, y=20)
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": 20}]}}]

    def test_with_expr(self):
        s = Steps().assign("init", x=10, y=expr("x + 1"))
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}, {"y": "${x + 1}"}]}}]

    def test_with_next(self):
        s = Steps().assign("init", x=10, next="done")
        d = _to_dict(s)
        assert d == [{"init": {"assign": [{"x": 10}], "next": "done"}}]

    def test_equivalent_to_step(self):
        """Alias produces same output as .step() with Assign."""
        alias = Steps().assign("init", x=10, y=20)
        explicit = Steps().step("init", Assign(x=10, y=20))
        assert alias.build() == explicit.build()

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="at least one assignment"):
            Steps().assign("init")

    def test_returns_self(self):
        s = Steps()
        result = s.assign("init", x=10)
        assert result is s


# =============================================================================
# .call()
# =============================================================================


class TestCallAlias:
    """Tests for Steps.call() alias method."""

    def test_simple_call(self):
        s = Steps().call("log", "sys.log", args={"text": "hello"})
        d = _to_dict(s)
        assert d == [{"log": {"call": "sys.log", "args": {"text": "hello"}}}]

    def test_with_result(self):
        s = Steps().call(
            "fetch", "http.get", args={"url": "https://example.com"}, result="resp"
        )
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

    def test_with_next(self):
        s = Steps().call("log", "sys.log", args={"text": "hi"}, next="done")
        d = _to_dict(s)
        assert d == [
            {
                "log": {
                    "call": "sys.log",
                    "args": {"text": "hi"},
                    "next": "done",
                }
            }
        ]

    def test_no_args(self):
        s = Steps().call("invoke", "my_subworkflow")
        d = _to_dict(s)
        assert d == [{"invoke": {"call": "my_subworkflow"}}]

    def test_equivalent_to_step(self):
        alias = Steps().call("log", "sys.log", args={"text": "hi"})
        explicit = Steps().step("log", Call("sys.log", args={"text": "hi"}))
        assert alias.build() == explicit.build()

    def test_empty_func_raises(self):
        with pytest.raises(ValueError, match="function name"):
            Steps().call("log", "")

    def test_returns_self(self):
        s = Steps()
        result = s.call("log", "sys.log")
        assert result is s


# =============================================================================
# .returns()
# =============================================================================


class TestReturnsAlias:
    """Tests for Steps.returns() alias method."""

    def test_string_value(self):
        s = Steps().returns("done", "ok")
        d = _to_dict(s)
        assert d == [{"done": {"return": "ok"}}]

    def test_expr_value(self):
        s = Steps().returns("done", expr("x + y"))
        d = _to_dict(s)
        assert d == [{"done": {"return": "${x + y}"}}]

    def test_none_value(self):
        """Return(None) — alias delegates correctly even with None.

        Note: model_dump(exclude_none=True) strips the return key when
        value is None. This is a known limitation of the underlying
        Return step class, not the alias. Verify alias matches .step().
        """
        alias = Steps().returns("done", None)
        explicit = Steps().step("done", Return(None))
        assert alias.build() == explicit.build()

    def test_dict_value(self):
        s = Steps().returns("done", {"status": "ok", "code": 200})
        d = _to_dict(s)
        assert d == [{"done": {"return": {"status": "ok", "code": 200}}}]

    def test_equivalent_to_step(self):
        alias = Steps().returns("done", "ok")
        explicit = Steps().step("done", Return("ok"))
        assert alias.build() == explicit.build()

    def test_returns_self(self):
        s = Steps()
        result = s.returns("done", "ok")
        assert result is s


# =============================================================================
# .raises()
# =============================================================================


class TestRaisesAlias:
    """Tests for Steps.raises() alias method."""

    def test_string_value(self):
        s = Steps().raises("fail", "something went wrong")
        d = _to_dict(s)
        assert d == [{"fail": {"raise": "something went wrong"}}]

    def test_dict_value(self):
        s = Steps().raises("fail", {"code": 404, "message": "not found"})
        d = _to_dict(s)
        assert d == [{"fail": {"raise": {"code": 404, "message": "not found"}}}]

    def test_expr_value(self):
        s = Steps().raises("fail", expr("e"))
        d = _to_dict(s)
        assert d == [{"fail": {"raise": "${e}"}}]

    def test_equivalent_to_step(self):
        alias = Steps().raises("fail", "error")
        explicit = Steps().step("fail", Raise("error"))
        assert alias.build() == explicit.build()

    def test_returns_self(self):
        s = Steps()
        result = s.raises("fail", "error")
        assert result is s


# =============================================================================
# .switch()
# =============================================================================


class TestSwitchAlias:
    """Tests for Steps.switch() alias method."""

    def test_basic_switch(self):
        s = Steps().switch(
            "check",
            [
                Condition(expr("x > 0"), next="positive"),
                Condition(True, next="negative"),
            ],
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

    def test_with_next(self):
        s = Steps().switch(
            "check",
            [
                Condition(expr("x > 0"), next="positive"),
            ],
            next="fallback",
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

    def test_condition_with_return(self):
        s = Steps().switch(
            "check",
            [
                Condition(expr("x > 0"), returns="positive"),
                Condition(True, returns="negative"),
            ],
        )
        d = _to_dict(s)
        assert d == [
            {
                "check": {
                    "switch": [
                        {"condition": "${x > 0}", "return": "positive"},
                        {"condition": True, "return": "negative"},
                    ]
                }
            }
        ]

    def test_equivalent_to_step(self):
        conds = [
            Condition(expr("x > 0"), next="positive"),
            Condition(True, next="negative"),
        ]
        alias = Steps().switch("check", conds)
        explicit = Steps().step("check", Switch(conds))
        assert alias.build() == explicit.build()

    def test_empty_conditions_raises(self):
        with pytest.raises(ValueError, match="at least one condition"):
            Steps().switch("check", [])

    def test_returns_self(self):
        s = Steps()
        result = s.switch("check", [Condition(True, next="end")])
        assert result is s

    def test_fixture_match(self):
        """Full switch workflow matches cdk/switch.yaml fixture."""
        s = (
            Steps()
            .assign("init", x=10)
            .switch(
                "check",
                [
                    Condition(expr("x > 0"), next="positive"),
                    Condition(True, next="negative"),
                ],
            )
            .returns("positive", "positive")
            .returns("negative", "negative")
        )
        expected = yaml.safe_load(load_fixture("cdk", "switch.yaml"))
        assert s.build() == expected


# =============================================================================
# .loop()
# =============================================================================


class TestLoopAlias:
    """Tests for Steps.loop() alias method."""

    def test_basic_loop(self):
        inner = Steps().call("log", "sys.log", args={"text": expr("item")})
        s = Steps().loop("loop", value="item", items=["a", "b", "c"], steps=inner)
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert s.build() == expected

    def test_loop_with_range(self):
        inner = Steps().call("log", "sys.log", args={"text": expr("i")})
        s = Steps().loop("loop", value="i", range=[0, 10], steps=inner)
        d = _to_dict(s)
        loop_body = d[0]["loop"]["for"]
        assert loop_body["value"] == "i"
        assert loop_body["range"] == [0, 10]

    def test_loop_with_index(self):
        inner = Steps().call("log", "sys.log", args={"text": expr("item")})
        s = Steps().loop(
            "loop", value="item", items=["a", "b"], index="idx", steps=inner
        )
        d = _to_dict(s)
        loop_body = d[0]["loop"]["for"]
        assert loop_body["index"] == "idx"

    def test_loop_with_lambda(self):
        """Lambda steps produce same output as explicit Steps."""
        s = Steps().loop(
            "loop",
            value="item",
            items=["a", "b", "c"],
            steps=lambda s: s.call("log", "sys.log", args={"text": expr("item")}),
        )
        expected = yaml.safe_load(load_fixture("cdk", "for_loop.yaml"))
        assert s.build() == expected

    def test_equivalent_to_step(self):
        inner = Steps().call("log", "sys.log", args={"text": expr("item")})
        alias = Steps().loop("loop", value="item", items=["a", "b", "c"], steps=inner)
        explicit = Steps().step(
            "loop",
            For(
                value="item",
                items=["a", "b", "c"],
                steps=inner,
            ),
        )
        assert alias.build() == explicit.build()

    def test_missing_items_and_range_raises(self):
        inner = Steps().assign("x", a=1)
        with pytest.raises(ValueError, match="items or range"):
            Steps().loop("loop", value="item", steps=inner)

    def test_returns_self(self):
        inner = Steps().assign("x", a=1)
        s = Steps()
        result = s.loop("loop", value="item", items=[1], steps=inner)
        assert result is s


# =============================================================================
# .parallel()
# =============================================================================


class TestParallelAlias:
    """Tests for Steps.parallel() alias method."""

    def test_basic_parallel(self):
        b1 = Steps().call("log1", "sys.log", args={"text": "branch 1"})
        b2 = Steps().call("log2", "sys.log", args={"text": "branch 2"})
        s = Steps().parallel(
            "fan_out", branches={"branch1": b1, "branch2": b2}, shared=["result"]
        )
        expected = yaml.safe_load(load_fixture("cdk", "alias_parallel.yaml"))
        assert s.build() == expected

    def test_with_exception_policy(self):
        b1 = Steps().assign("x", a=1)
        b2 = Steps().assign("y", b=2)
        s = Steps().parallel(
            "p", branches={"b1": b1, "b2": b2}, exception_policy="continueAll"
        )
        d = _to_dict(s)
        assert d[0]["p"]["parallel"]["exception_policy"] == "continueAll"

    def test_with_concurrency_limit(self):
        b1 = Steps().assign("x", a=1)
        b2 = Steps().assign("y", b=2)
        s = Steps().parallel("p", branches={"b1": b1, "b2": b2}, concurrency_limit=2)
        d = _to_dict(s)
        assert d[0]["p"]["parallel"]["concurrency_limit"] == 2

    def test_equivalent_to_step(self):
        b1 = Steps().call("log1", "sys.log", args={"text": "b1"})
        b2 = Steps().call("log2", "sys.log", args={"text": "b2"})
        alias = Steps().parallel("p", branches={"b1": b1, "b2": b2})
        explicit = Steps().step("p", Parallel(branches={"b1": b1, "b2": b2}))
        assert alias.build() == explicit.build()

    def test_empty_branches_raises(self):
        with pytest.raises(ValueError, match="at least one branch"):
            Steps().parallel("p", branches={})

    def test_returns_self(self):
        b1 = Steps().assign("x", a=1)
        s = Steps()
        result = s.parallel("p", branches={"b1": b1})
        assert result is s


# =============================================================================
# .do_try()
# =============================================================================


class TestDoTryAlias:
    """Tests for Steps.do_try() alias method."""

    def test_try_with_retry_and_except(self):
        body = Steps().call(
            "fetch", "http.get", args={"url": "https://example.com"}, result="response"
        )
        handler = Steps().raises("handle", expr("e"))
        s = Steps().do_try(
            "safe_call",
            steps=body,
            retry=Retry(
                expr("e.code == 429"),
                max_retries=3,
                backoff=Backoff(
                    initial_delay=1,
                    max_delay=30,
                    multiplier=2,
                ),
            ),
            error_steps=handler,
        )
        expected = yaml.safe_load(load_fixture("cdk", "alias_try.yaml"))
        assert s.build() == expected

    def test_try_without_retry(self):
        body = Steps().call("fetch", "http.get", args={"url": "https://example.com"})
        handler = Steps().raises("handle", expr("e"))
        s = Steps().do_try("safe", steps=body, error_steps=handler)
        d = _to_dict(s)
        step_body = d[0]["safe"]
        assert "retry" not in step_body
        assert "except" in step_body

    def test_try_without_except(self):
        body = Steps().call("fetch", "http.get", args={"url": "https://example.com"})
        s = Steps().do_try(
            "safe", steps=body, retry=Retry("http.default_retry", max_retries=3)
        )
        d = _to_dict(s)
        step_body = d[0]["safe"]
        assert "retry" in step_body
        assert "except" not in step_body

    def test_try_with_steps_body(self):
        """Multi-step body produces TryStepsBody, not TryCallBody."""
        body = (
            Steps().assign("init", x=1).call("log", "sys.log", args={"text": expr("x")})
        )
        s = Steps().do_try("safe", steps=body)
        d = _to_dict(s)
        try_body = d[0]["safe"]["try"]
        assert "steps" in try_body

    def test_equivalent_to_step(self):
        body = Steps().call("fetch", "http.get", args={"url": "https://example.com"})
        alias = Steps().do_try("safe", steps=body)
        explicit = Steps().step("safe", Try(steps=body))
        assert alias.build() == explicit.build()

    def test_returns_self(self):
        body = Steps().assign("x", a=1)
        s = Steps()
        result = s.do_try("safe", steps=body)
        assert result is s


# =============================================================================
# .nested()
# =============================================================================


class TestNestedAlias:
    """Tests for Steps.nested() alias method."""

    def test_basic_nested(self):
        inner = Steps().assign("inner1", x=1).returns("inner2", expr("x"))
        s = Steps().nested("group", steps=inner, next="done")
        expected = yaml.safe_load(load_fixture("cdk", "alias_nested.yaml"))
        assert s.build() == expected

    def test_without_next(self):
        inner = Steps().assign("inner", x=1)
        s = Steps().nested("group", steps=inner)
        d = _to_dict(s)
        assert "next" not in d[0]["group"]

    def test_with_lambda(self):
        s = Steps().nested(
            "group",
            steps=lambda s: s.assign("inner", x=1).returns("done", expr("x")),
            next="end",
        )
        d = _to_dict(s)
        assert d[0]["group"]["steps"] == [
            {"inner": {"assign": [{"x": 1}]}},
            {"done": {"return": "${x}"}},
        ]

    def test_equivalent_to_step(self):
        inner = Steps().assign("inner", x=1)
        alias = Steps().nested("group", steps=inner)
        explicit = Steps().step("group", NestedSteps(steps=inner))
        assert alias.build() == explicit.build()

    def test_returns_self(self):
        inner = Steps().assign("x", a=1)
        s = Steps()
        result = s.nested("group", steps=inner)
        assert result is s


# =============================================================================
# Chaining — multiple aliases in one chain
# =============================================================================


class TestAliasChaining:
    """Tests for chaining multiple alias methods."""

    def test_full_chain(self):
        """Multi-step chain matches fixture."""
        inner = Steps().call("log_item", "sys.log", args={"text": expr("item")})
        s = (
            Steps()
            .assign("init", x=10, y=20)
            .call("log", "sys.log", args={"text": expr("x")})
            .switch(
                "check",
                [
                    Condition(expr("x > 0"), next="positive"),
                    Condition(True, next="negative"),
                ],
            )
            .loop("iterate", value="item", items=["a", "b", "c"], steps=inner)
            .returns("done", expr("x + y"))
        )
        expected = yaml.safe_load(load_fixture("cdk", "alias_chained.yaml"))
        assert s.build() == expected

    def test_chain_length(self):
        s = Steps().assign("a", x=1).call("b", "sys.log").returns("c", "ok")
        assert len(s) == 3

    def test_mixed_step_and_alias(self):
        """Alias methods and .step() can be mixed freely."""
        s = (
            Steps()
            .assign("init", x=10)
            .step("log", Call("sys.log", args={"text": expr("x")}))
            .returns("done", expr("x"))
        )
        assert len(s) == 3
        d = _to_dict(s)
        assert d[0] == {"init": {"assign": [{"x": 10}]}}
        assert d[1] == {"log": {"call": "sys.log", "args": {"text": "${x}"}}}
        assert d[2] == {"done": {"return": "${x}"}}

    def test_merge_with_aliases(self):
        """merge() works with Steps built via aliases."""
        common = Steps().call("log", "sys.log", args={"text": "start"})
        main = Steps().merge(common).assign("init", x=10).returns("done", expr("x"))
        assert len(main) == 3

    def test_alias_chain_matches_explicit_step_chain(self):
        """Full chain via aliases matches full chain via .step()."""
        alias = (
            Steps()
            .assign("init", x=10, y=20)
            .call("log", "sys.log", args={"text": expr("x")})
            .returns("done", expr("x + y"))
        )
        explicit = (
            Steps()
            .step("init", Assign(x=10, y=20))
            .step("log", Call("sys.log", args={"text": expr("x")}))
            .step("done", Return(expr("x + y")))
        )
        assert alias.build() == explicit.build()
