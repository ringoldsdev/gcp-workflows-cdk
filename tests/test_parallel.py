import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, ParallelStep
from conftest import parse_fixture


def test_parallel_branches():
    wf = parse_fixture("parallel", "branches.yaml")
    assert len(wf.steps) == 3
    parallel_body = wf.steps[1].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.shared == ["results"]
    assert len(parallel_body.parallel.branches) == 2


def test_parallel_for():
    wf = parse_fixture("parallel", "for.yaml")
    assert len(wf.steps) == 3
    parallel_body = wf.steps[1].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.shared == ["total"]
    assert parallel_body.parallel.for_.value == "item"


def test_parallel_exception_policy():
    wf = parse_fixture("parallel", "exception_policy.yaml")
    parallel_body = wf.steps[0].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.exception_policy == "continueAll"
    assert len(parallel_body.parallel.branches) == 2


def test_parallel_concurrency():
    wf = parse_fixture("parallel", "concurrency.yaml")
    parallel_body = wf.steps[0].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.concurrency_limit == 3
    assert parallel_body.parallel.for_.value == "i"


def test_parallel_1_branch():
    with pytest.raises(ValidationError):
        parse_fixture("parallel", "1_branch.yaml")


def test_parallel_11_branches():
    with pytest.raises(ValidationError):
        parse_fixture("parallel", "11_branches.yaml")


def test_parallel_both_branches_and_for():
    with pytest.raises(ValidationError):
        parse_fixture("parallel", "both_branches_and_for.yaml")
