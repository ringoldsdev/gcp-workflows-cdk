import textwrap
import pytest
from pydantic import ValidationError

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cloud_workflows.models import parse_workflow, ParallelStep


def test_parallel_branches():
    yaml_str = textwrap.dedent("""\
        - init:
            assign:
              - results: {}
        - parallel_work:
            parallel:
              shared: [results]
              branches:
                - branch_a:
                    steps:
                      - get_a:
                          call: http.get
                          args:
                            url: https://example.com/a
                          result: a
                      - save_a:
                          assign:
                            - results.a: ${a.body}
                - branch_b:
                    steps:
                      - get_b:
                          call: http.get
                          args:
                            url: https://example.com/b
                          result: b
                      - save_b:
                          assign:
                            - results.b: ${b.body}
        - done:
            return: ${results}
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 3
    parallel_body = wf.steps[1].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.shared == ["results"]
    assert len(parallel_body.parallel.branches) == 2


def test_parallel_for():
    yaml_str = textwrap.dedent("""\
        - init:
            assign:
              - total: 0
              - items: [1, 2, 3, 4, 5]
        - process:
            parallel:
              shared: [total]
              for:
                value: item
                in: ${items}
                steps:
                  - add:
                      assign:
                        - total: ${total + item}
        - done:
            return: ${total}
    """)
    wf = parse_workflow(yaml_str)
    assert len(wf.steps) == 3
    parallel_body = wf.steps[1].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.shared == ["total"]
    assert parallel_body.parallel.for_.value == "item"


def test_parallel_exception_policy():
    yaml_str = textwrap.dedent("""\
        - work:
            parallel:
              exception_policy: continueAll
              shared: [results]
              branches:
                - safe:
                    steps:
                      - ok:
                          assign:
                            - results: ["ok"]
                - risky:
                    steps:
                      - fail:
                          raise: "oops"
    """)
    wf = parse_workflow(yaml_str)
    parallel_body = wf.steps[0].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.exception_policy == "continueAll"
    assert len(parallel_body.parallel.branches) == 2


def test_parallel_concurrency():
    yaml_str = textwrap.dedent("""\
        - work:
            parallel:
              concurrency_limit: 3
              for:
                value: i
                range: [1, 20]
                steps:
                  - process:
                      call: http.get
                      args:
                        url: '${"https://example.com/item/" + string(i)}'
    """)
    wf = parse_workflow(yaml_str)
    parallel_body = wf.steps[0].body
    assert isinstance(parallel_body, ParallelStep)
    assert parallel_body.parallel.concurrency_limit == 3
    assert parallel_body.parallel.for_.value == "i"


def test_parallel_1_branch():
    yaml_str = textwrap.dedent("""\
        - work:
            parallel:
              branches:
                - only_one:
                    steps:
                      - step:
                          assign:
                            - x: 1
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)


def test_parallel_11_branches():
    branches = "\n".join(
        f"        - b{i}:\n            steps:\n              - s:\n                  assign:\n                    - x: {i}"
        for i in range(1, 12)
    )
    yaml_str = f"- work:\n    parallel:\n      branches:\n{branches}"
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)


def test_parallel_both_branches_and_for():
    yaml_str = textwrap.dedent("""\
        - work:
            parallel:
              branches:
                - b1:
                    steps:
                      - s:
                          assign:
                            - x: 1
                - b2:
                    steps:
                      - s:
                          assign:
                            - x: 2
              for:
                value: i
                range: [1, 5]
                steps:
                  - s:
                      assign:
                        - y: 1
    """)
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)
