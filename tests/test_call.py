"""Tests for CallStep validation."""

import textwrap

import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, CallStep


def parse(yaml_str: str):
    """Helper: dedent + parse a YAML string."""
    return parse_workflow(textwrap.dedent(yaml_str))


def test_call_http_get():
    """VALID: http.get call with args and result."""
    wf = parse("""\
        - fetch:
            call: http.get
            args:
              url: https://example.com/api
            result: response
    """)
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "http.get"
    assert body.result == "response"


def test_call_http_post_auth():
    """VALID: http.post call with auth and body in args."""
    wf = parse("""\
        - post_data:
            call: http.post
            args:
              url: https://us-central1-myproject.cloudfunctions.net/myfunc
              auth:
                type: OIDC
              body:
                message: "Hello World"
            result: the_message
    """)
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
    wf = parse("""\
        - get_time:
            call: sys.now
            result: current_time
    """)
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "sys.now"
    assert body.args is None
    assert body.result == "current_time"


def test_call_no_result():
    """VALID: result is optional."""
    wf = parse("""\
        - log_it:
            call: sys.log
            args:
              data: "hello"
    """)
    step = wf.steps[0]
    body = step.body
    assert isinstance(body, CallStep)
    assert body.call == "sys.log"
    assert body.args == {"data": "hello"}
    assert body.result is None


def test_call_subworkflow():
    """VALID: Form B with subworkflow call."""
    wf = parse("""\
        main:
            steps:
                - invoke:
                    call: my_helper
                    args:
                        x: 42
                    result: output
                - done:
                    return: ${output}

        my_helper:
            params: [x]
            steps:
                - compute:
                    return: ${x * 2}
    """)
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
