"""Integration tests for complex, multi-feature workflows."""

import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow
from conftest import parse_fixture


def test_full_workflow():
    """VALID: full workflow with params, assign, switch, for, try/retry/except, call, and return."""
    wf = parse_fixture("integration", "full_workflow.yaml")
    assert "main" in wf.workflows
    main = wf.workflows["main"]
    assert main.params == ["args"]
    assert len(main.steps) == 4
    assert main.steps[0].name == "init"
    assert main.steps[1].name == "validate"
    assert main.steps[2].name == "process"
    assert main.steps[3].name == "done"

    # Verify the for loop step
    for_body = main.steps[2].body.for_
    assert for_body.value == "item"
    assert len(for_body.steps) == 2

    # Verify try/retry/except inside for loop
    try_step = for_body.steps[0].body
    assert try_step.try_.call == "http.get"
    assert try_step.retry == "${http.default_retry}"
    assert try_step.except_ is not None
    assert try_step.except_.as_ == "e"
    assert len(try_step.except_.steps) == 2

    # Verify final return is a map
    done_body = main.steps[3].body
    assert isinstance(done_body.return_, dict)


def test_parallel_with_try():
    """VALID: parallel branches with nested try/except and shared variables."""
    wf = parse_fixture("integration", "parallel_with_try.yaml")
    assert len(wf.steps) == 3
    assert wf.steps[0].name == "init"
    assert wf.steps[1].name == "parallel_fetch"
    assert wf.steps[2].name == "done"

    # Verify parallel structure
    parallel_body = wf.steps[1].body.parallel
    assert parallel_body.shared == ["results"]
    assert len(parallel_body.branches) == 2

    # Verify branch names and structure
    branch_a = parallel_body.branches[0]
    branch_b = parallel_body.branches[1]
    assert branch_a.name == "api_a"
    assert branch_b.name == "api_b"
    assert len(branch_a.steps) == 2
    assert len(branch_b.steps) == 2

    # Verify try/except in branch A (has retry)
    try_a = branch_a.steps[0].body
    assert try_a.try_.call == "http.get"
    assert try_a.retry == "${http.default_retry}"
    assert try_a.except_ is not None
    assert try_a.except_.as_ == "e"

    # Verify try/except in branch B (no retry)
    try_b = branch_b.steps[0].body
    assert try_b.try_.call == "http.get"
    assert try_b.retry is None
    assert try_b.except_ is not None
    assert try_b.except_.as_ == "e"
