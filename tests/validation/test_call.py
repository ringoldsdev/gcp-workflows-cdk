"""Tests for CallStep validation."""

import pytest
from pydantic import ValidationError

from cloud_workflows.models import parse_workflow, CallStep
from conftest import parse_fixture


def test_call_http_get():
    """VALID: http.get call with args and result."""
    wf = parse_fixture("call", "http_get.yaml")
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "http.get"
    assert body.result == "response"


def test_call_http_post_auth():
    """VALID: http.post call with auth and body in args."""
    wf = parse_fixture("call", "http_post_auth.yaml")
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "http.post"
    assert body.result == "the_message"
    assert body.args["url"] == "https://us-central1-myproject.cloudfunctions.net/myfunc"
    assert body.args["auth"] == {"type": "OIDC"}
    assert body.args["body"] == {"message": "Hello World"}


def test_call_no_args():
    """VALID: args is optional."""
    wf = parse_fixture("call", "no_args.yaml")
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "sys.now"
    assert body.args is None
    assert body.result == "current_time"


def test_call_no_result():
    """VALID: result is optional."""
    wf = parse_fixture("call", "no_result.yaml")
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "sys.log"
    assert body.args == {"data": "hello"}
    assert body.result is None


def test_call_subworkflow():
    """VALID: Form B with subworkflow call."""
    wf = parse_fixture("call", "subworkflow.yaml")
    # Form B: SubworkflowsWorkflow
    main = wf.workflows["main"]
    invoke_step = main.steps[0]
    body = invoke_step.body
    assert isinstance(body, CallStep)
    assert body.call == "my_helper"
    assert body.args == {"x": 42}
    assert body.result == "output"

    helper = wf.workflows["my_helper"]
    assert helper.params == ["x"]
    assert len(helper.steps) == 1
