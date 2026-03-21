import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import (
    parse_workflow,
    TryStep,
    TryCallBody,
    TryStepsBody,
    RetryConfig,
)


def test_try_except_call():
    """VALID - try with single call body and except handler."""
    yaml_str = textwrap.dedent("""\
        - attempt:
            try:
              call: http.get
              args:
                url: https://example.com/might-fail
              result: response
            except:
              as: e
              steps:
                - log:
                    call: sys.log
                    args:
                      data: ${e.message}
                - default:
                    return: "failed"
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "attempt"
    body = step.body
    assert isinstance(body, TryStep)
    assert isinstance(body.try_, TryCallBody)
    assert body.try_.call == "http.get"
    assert body.try_.args == {"url": "https://example.com/might-fail"}
    assert body.try_.result == "response"
    assert body.except_ is not None
    assert body.except_.as_ == "e"
    assert len(body.except_.steps) == 2
    assert body.except_.steps[0].name == "log"
    assert body.except_.steps[1].name == "default"


def test_try_except_steps():
    """VALID - try with steps block and except handler."""
    yaml_str = textwrap.dedent("""\
        - attempt:
            try:
              steps:
                - get_token:
                    call: http.post
                    args:
                      url: https://auth.example.com/token
                    result: token
                - use_token:
                    call: http.get
                    args:
                      url: https://api.example.com/data
                      headers:
                        Authorization: '${"Bearer " + token.body.access_token}'
                    result: data
            except:
              as: e
              steps:
                - handle:
                    return: ${e.message}
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "attempt"
    body = step.body
    assert isinstance(body, TryStep)
    assert isinstance(body.try_, TryStepsBody)
    assert len(body.try_.steps) == 2
    assert body.try_.steps[0].name == "get_token"
    assert body.try_.steps[1].name == "use_token"
    assert body.except_ is not None
    assert body.except_.as_ == "e"
    assert len(body.except_.steps) == 1
    assert body.except_.steps[0].name == "handle"


def test_try_retry_predefined():
    """VALID - try with a predefined retry policy expression."""
    yaml_str = textwrap.dedent("""\
        - reliable:
            try:
              call: http.get
              args:
                url: https://example.com/api
              result: response
            retry: ${http.default_retry}
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "reliable"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.try_.call == "http.get"
    assert body.retry == "${http.default_retry}"


def test_try_retry_custom():
    """VALID - try with a custom retry policy."""
    yaml_str = textwrap.dedent("""\
        - reliable:
            try:
              call: http.post
              args:
                url: https://example.com/api
                body:
                  data: "important"
              result: response
            retry:
              predicate: ${http.default_retry_predicate}
              max_retries: 5
              backoff:
                initial_delay: 1
                max_delay: 60
                multiplier: 2
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "reliable"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.try_.call == "http.post"
    assert body.try_.result == "response"
    assert isinstance(body.retry, RetryConfig)
    assert body.retry.predicate == "${http.default_retry_predicate}"
    assert body.retry.max_retries == 5
    assert body.retry.backoff.initial_delay == 1
    assert body.retry.backoff.max_delay == 60
    assert body.retry.backoff.multiplier == 2


def test_try_retry_except_combined():
    """VALID - try with both retry and except."""
    yaml_str = textwrap.dedent("""\
        - robust:
            try:
              call: http.get
              args:
                url: https://example.com/api
              result: response
            retry:
              predicate: ${http.default_retry_predicate}
              max_retries: 3
              backoff:
                initial_delay: 1
                max_delay: 30
                multiplier: 2
            except:
              as: e
              steps:
                - fallback:
                    return: "all retries failed"
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 1
    step = wf.steps[0]
    assert step.name == "robust"
    body = step.body
    assert isinstance(body, TryStep)
    assert body.try_.call == "http.get"
    # Verify retry
    assert isinstance(body.retry, RetryConfig)
    assert body.retry.predicate == "${http.default_retry_predicate}"
    assert body.retry.max_retries == 3
    assert body.retry.backoff.initial_delay == 1
    assert body.retry.backoff.max_delay == 30
    assert body.retry.backoff.multiplier == 2
    # Verify except
    assert body.except_ is not None
    assert body.except_.as_ == "e"
    assert len(body.except_.steps) == 1
    assert body.except_.steps[0].name == "fallback"
