import pytest
from pydantic import ValidationError

from cloud_workflows.models import (
    parse_workflow,
    TryStep,
    TryCallBody,
    TryStepsBody,
    RetryConfig,
)
from conftest import parse_fixture


def test_try_except_call():
    """VALID - try with single call body and except handler."""
    wf = parse_fixture("try", "except_call.yaml")
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "attempt"
    body = step.body
    assert isinstance(body, TryStep)
    assert isinstance(body.steps, TryCallBody)
    assert body.steps.call == "http.get"
    assert body.steps.args == {"url": "https://example.com/might-fail"}
    assert body.steps.result == "response"
    assert body.error_steps is not None
    assert body.error_steps.alias == "e"
    assert len(body.error_steps.steps) == 2
    assert body.error_steps.steps[0].name == "log"
    assert body.error_steps.steps[1].name == "default"


def test_try_except_steps():
    """VALID - try with steps block and except handler."""
    wf = parse_fixture("try", "except_steps.yaml")
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "attempt"
    body = step.body
    assert isinstance(body, TryStep)
    assert isinstance(body.steps, TryStepsBody)
    assert len(body.steps.steps) == 2
    assert body.steps.steps[0].name == "get_token"
    assert body.steps.steps[1].name == "use_token"
    assert body.error_steps is not None
    assert body.error_steps.alias == "e"
    assert len(body.error_steps.steps) == 1
    assert body.error_steps.steps[0].name == "handle"


def test_try_retry_predefined():
    """VALID - try with a predefined retry policy expression."""
    wf = parse_fixture("try", "retry_predefined.yaml")
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "reliable"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.steps.call == "http.get"
    assert body.retry == "${http.default_retry}"


def test_try_retry_custom():
    """VALID - try with a custom retry policy."""
    wf = parse_fixture("try", "retry_custom.yaml")
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "reliable"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.steps.call == "http.post"
    assert body.steps.result == "response"
    assert isinstance(body.retry, RetryConfig)
    assert body.retry.predicate == "${http.default_retry_predicate}"
    assert body.retry.max_retries == 5
    assert body.retry.backoff.initial_delay == 1
    assert body.retry.backoff.max_delay == 60
    assert body.retry.backoff.multiplier == 2


def test_try_retry_except_combined():
    """VALID - try with both retry and except."""
    wf = parse_fixture("try", "retry_except_combined.yaml")
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "robust"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.steps.call == "http.get"
    # Verify retry
    assert isinstance(body.retry, RetryConfig)
    assert body.retry.predicate == "${http.default_retry_predicate}"
    assert body.retry.max_retries == 3
    assert body.retry.backoff.initial_delay == 1
    assert body.retry.backoff.max_delay == 30
    assert body.retry.backoff.multiplier == 2
    # Verify except
    assert body.error_steps is not None
    assert body.error_steps.alias == "e"
    assert len(body.error_steps.steps) == 1
    assert body.error_steps.steps[0].name == "fallback"
