"""Tests for cloud_workflows.consts — stdlib function registry and helpers."""

from __future__ import annotations

from cloud_workflows.consts import (
    EXPRESSION_BUILTINS,
    RETRY_PREDICATES,
    STDLIB_FUNCTIONS,
    STDLIB_NAMESPACES,
    is_expression_builtin,
    is_retry_predicate,
    is_stdlib_call,
    is_stdlib_namespace,
)


# ---------------------------------------------------------------------------
# STDLIB_FUNCTIONS
# ---------------------------------------------------------------------------


class TestStdlibFunctions:
    """Verify the STDLIB_FUNCTIONS frozenset."""

    def test_is_frozenset(self):
        assert isinstance(STDLIB_FUNCTIONS, frozenset)

    def test_count(self):
        # 50 documented stdlib callable functions as of 2026-03
        assert len(STDLIB_FUNCTIONS) == 50

    def test_http_get_present(self):
        assert "http.get" in STDLIB_FUNCTIONS

    def test_http_post_present(self):
        assert "http.post" in STDLIB_FUNCTIONS

    def test_sys_log_present(self):
        assert "sys.log" in STDLIB_FUNCTIONS

    def test_uuid_generate_present(self):
        assert "uuid.generate" in STDLIB_FUNCTIONS

    def test_text_url_encode_plus_present(self):
        assert "text.url_encode_plus" in STDLIB_FUNCTIONS

    def test_experimental_executions_map_present(self):
        assert "experimental.executions.map" in STDLIB_FUNCTIONS

    def test_all_have_dot(self):
        """Every stdlib function should be namespaced (contains a dot)."""
        for fn in STDLIB_FUNCTIONS:
            assert "." in fn, f"{fn!r} has no dot"

    def test_no_retry_predicates_in_stdlib(self):
        """Retry predicates are NOT callable functions."""
        assert "http.default_retry" not in STDLIB_FUNCTIONS
        assert "retry.always" not in STDLIB_FUNCTIONS

    def test_base64_module(self):
        base64_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("base64.")}
        assert base64_fns == {"base64.decode", "base64.encode"}

    def test_events_module(self):
        events_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("events.")}
        assert events_fns == {
            "events.await_callback",
            "events.create_callback_endpoint",
        }

    def test_hash_module(self):
        hash_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("hash.")}
        assert hash_fns == {"hash.compute_checksum", "hash.compute_hmac"}

    def test_http_module(self):
        http_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("http.")}
        assert http_fns == {
            "http.delete",
            "http.get",
            "http.patch",
            "http.post",
            "http.put",
            "http.request",
        }

    def test_json_module(self):
        json_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("json.")}
        assert json_fns == {"json.decode", "json.encode", "json.encode_to_string"}

    def test_list_module(self):
        list_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("list.")}
        assert list_fns == {"list.concat", "list.prepend"}

    def test_map_module(self):
        map_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("map.")}
        assert map_fns == {"map.delete", "map.get", "map.merge", "map.merge_nested"}

    def test_math_module(self):
        math_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("math.")}
        assert math_fns == {"math.abs", "math.floor", "math.max", "math.min"}

    def test_sys_module(self):
        sys_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("sys.")}
        assert sys_fns == {
            "sys.get_env",
            "sys.log",
            "sys.now",
            "sys.sleep",
            "sys.sleep_until",
        }

    def test_text_module(self):
        text_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("text.")}
        assert text_fns == {
            "text.decode",
            "text.encode",
            "text.find_all",
            "text.find_all_regex",
            "text.match_regex",
            "text.replace_all",
            "text.replace_all_regex",
            "text.split",
            "text.substring",
            "text.to_lower",
            "text.to_upper",
            "text.url_decode",
            "text.url_encode",
            "text.url_encode_plus",
        }

    def test_time_module(self):
        time_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("time.")}
        assert time_fns == {"time.format", "time.parse"}

    def test_uuid_module(self):
        uuid_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("uuid.")}
        assert uuid_fns == {"uuid.generate"}

    def test_experimental_module(self):
        exp_fns = {f for f in STDLIB_FUNCTIONS if f.startswith("experimental.")}
        assert exp_fns == {
            "experimental.executions.execution_error",
            "experimental.executions.map",
            "experimental.executions.run",
        }


# ---------------------------------------------------------------------------
# RETRY_PREDICATES
# ---------------------------------------------------------------------------


class TestRetryPredicates:
    """Verify the RETRY_PREDICATES frozenset."""

    def test_is_frozenset(self):
        assert isinstance(RETRY_PREDICATES, frozenset)

    def test_count(self):
        assert len(RETRY_PREDICATES) == 7

    def test_http_default_retry_present(self):
        assert "http.default_retry" in RETRY_PREDICATES

    def test_http_default_retry_non_idempotent_present(self):
        assert "http.default_retry_non_idempotent" in RETRY_PREDICATES

    def test_http_default_retry_predicate_present(self):
        assert "http.default_retry_predicate" in RETRY_PREDICATES

    def test_http_default_retry_predicate_non_idempotent_present(self):
        assert "http.default_retry_predicate_non_idempotent" in RETRY_PREDICATES

    def test_retry_always_present(self):
        assert "retry.always" in RETRY_PREDICATES

    def test_retry_default_backoff_present(self):
        assert "retry.default_backoff" in RETRY_PREDICATES

    def test_retry_never_present(self):
        assert "retry.never" in RETRY_PREDICATES

    def test_no_overlap_with_stdlib(self):
        """Retry predicates and stdlib functions should be disjoint."""
        overlap = RETRY_PREDICATES & STDLIB_FUNCTIONS
        assert overlap == set(), f"Unexpected overlap: {overlap}"


# ---------------------------------------------------------------------------
# EXPRESSION_BUILTINS
# ---------------------------------------------------------------------------


class TestExpressionBuiltins:
    """Verify the EXPRESSION_BUILTINS frozenset."""

    def test_is_frozenset(self):
        assert isinstance(EXPRESSION_BUILTINS, frozenset)

    def test_count(self):
        assert len(EXPRESSION_BUILTINS) == 8

    def test_expected_members(self):
        assert EXPRESSION_BUILTINS == {
            "bool",
            "double",
            "int",
            "keys",
            "len",
            "not",
            "string",
            "type",
        }

    def test_no_dots(self):
        """Expression builtins are bare names (no namespace)."""
        for name in EXPRESSION_BUILTINS:
            assert "." not in name, f"{name!r} should not contain a dot"


# ---------------------------------------------------------------------------
# STDLIB_NAMESPACES
# ---------------------------------------------------------------------------


class TestStdlibNamespaces:
    """Verify the STDLIB_NAMESPACES frozenset."""

    def test_is_frozenset(self):
        assert isinstance(STDLIB_NAMESPACES, frozenset)

    def test_count(self):
        assert len(STDLIB_NAMESPACES) == 14

    def test_expected_members(self):
        assert STDLIB_NAMESPACES == {
            "base64",
            "events",
            "experimental.executions",
            "hash",
            "http",
            "json",
            "list",
            "map",
            "math",
            "retry",
            "sys",
            "text",
            "time",
            "uuid",
        }

    def test_every_stdlib_fn_has_matching_namespace(self):
        """Every stdlib function should belong to a known namespace."""
        for fn in STDLIB_FUNCTIONS:
            matched = any(fn.startswith(ns + ".") for ns in STDLIB_NAMESPACES)
            assert matched, f"{fn!r} has no matching namespace"

    def test_every_retry_predicate_has_matching_namespace(self):
        """Every retry predicate should belong to a known namespace."""
        for pred in RETRY_PREDICATES:
            matched = any(pred.startswith(ns + ".") for ns in STDLIB_NAMESPACES)
            assert matched, f"{pred!r} has no matching namespace"


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """Verify the convenience helper functions."""

    def test_is_stdlib_call_true(self):
        assert is_stdlib_call("http.get") is True

    def test_is_stdlib_call_false(self):
        assert is_stdlib_call("my_subworkflow") is False

    def test_is_stdlib_call_retry_is_false(self):
        assert is_stdlib_call("http.default_retry") is False

    def test_is_retry_predicate_true(self):
        assert is_retry_predicate("http.default_retry") is True

    def test_is_retry_predicate_false(self):
        assert is_retry_predicate("http.get") is False

    def test_is_expression_builtin_true(self):
        assert is_expression_builtin("len") is True

    def test_is_expression_builtin_false(self):
        assert is_expression_builtin("http.get") is False

    def test_is_stdlib_namespace_true(self):
        assert is_stdlib_namespace("http") is True

    def test_is_stdlib_namespace_false(self):
        assert is_stdlib_namespace("foobar") is False

    def test_is_stdlib_namespace_dotted(self):
        assert is_stdlib_namespace("experimental.executions") is True
