"""Tests for programmatic workflow construction and serialization (CDK layer).

Consolidated from the original test_cdk.py:
- Removed 14 test_to_dict_* methods (strict subsets of test_yaml_matches_fixture)
- Removed 7 TestDictRoundTrip tests (already covered by fixture match + parsing tests)
- Removed 7 TestConstructionValidation tests (duplicate of YAML-based validation tests)
- Merged small 2-test classes into TestCdkEdgeCases

Each test constructs a workflow programmatically using the Pydantic model classes,
serializes via to_yaml()/to_dict(), and verifies:
  - YAML output matches the corresponding fixture file
  - analyze_yaml() on the serialized YAML passes all 3 validation stages
  - analyze_workflow() on the model directly passes all 3 validation stages
"""

import pytest
import yaml

from cloud_workflows import (
    # Model types
    SimpleWorkflow,
    SubworkflowsWorkflow,
    WorkflowDefinition,
    Step,
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SwitchStep,
    SwitchCondition,
    ForStep,
    ForBody,
    ParallelStep,
    ParallelBody,
    Branch,
    TryStep,
    TryCallBody,
    TryStepsBody,
    ExceptBody,
    RetryConfig,
    BackoffConfig,
    NestedStepsStep,
    # Helpers
    expr,
    to_yaml,
    # Analysis
    analyze_yaml,
    analyze_workflow,
)

from conftest import load_fixture, parse_fixture, FIXTURES_DIR


# =============================================================================
# Helpers
# =============================================================================


def normalize_yaml(yaml_str: str) -> dict | list:
    """Parse YAML string to Python object for structural comparison."""
    return yaml.safe_load(yaml_str)


def assert_yaml_matches_fixture(workflow, *fixture_path_parts):
    """Assert that a workflow's to_yaml() output matches a fixture file structurally."""
    expected_str = load_fixture(*fixture_path_parts)
    expected = normalize_yaml(expected_str)
    actual = normalize_yaml(workflow.to_yaml())
    assert actual == expected, (
        f"YAML mismatch for fixture {'/'.join(fixture_path_parts)}:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


def assert_passes_analysis(workflow):
    """Assert that analyze_workflow() and analyze_yaml() both pass."""
    # Direct model analysis (no YAML round-trip)
    result = analyze_workflow(workflow)
    assert result.is_valid, f"analyze_workflow failed:\n  errors: {result.errors}"

    # YAML round-trip analysis
    yaml_str = workflow.to_yaml()
    result2 = analyze_yaml(yaml_str)
    assert result2.is_valid, (
        f"analyze_yaml failed on serialized YAML:\n"
        f"  errors: {result2.errors}\n"
        f"  yaml:\n{yaml_str}"
    )


# =============================================================================
# Test: Simple assign + return (Form A)
# =============================================================================


class TestSimpleAssign:
    """Programmatic construction of a simple assign+return workflow."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 10}, {"y": 20}])),
                Step(name="done", body=ReturnStep(returns=expr("x + y"))),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "simple_assign.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_model_structure(self, workflow):
        assert isinstance(workflow, SimpleWorkflow)
        assert len(workflow.steps) == 2
        assert isinstance(workflow.steps[0].body, AssignStep)
        assert isinstance(workflow.steps[1].body, ReturnStep)


# =============================================================================
# Test: Subworkflows (Form B)
# =============================================================================


class TestSubworkflows:
    """Programmatic construction of a Form B workflow with subworkflows."""

    @pytest.fixture
    def workflow(self):
        return SubworkflowsWorkflow(
            workflows={
                "main": WorkflowDefinition(
                    steps=[
                        Step(
                            name="call_helper",
                            body=CallStep(
                                call="helper", args={"input": "test"}, result="res"
                            ),
                        ),
                        Step(name="done", body=ReturnStep(returns=expr("res"))),
                    ]
                ),
                "helper": WorkflowDefinition(
                    params=["input"],
                    steps=[
                        Step(
                            name="log",
                            body=CallStep(call="sys.log", args={"text": expr("input")}),
                        ),
                        Step(name="done", body=ReturnStep(returns="ok")),
                    ],
                ),
            }
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "subworkflows.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_model_structure(self, workflow):
        assert isinstance(workflow, SubworkflowsWorkflow)
        assert "main" in workflow.workflows
        assert "helper" in workflow.workflows
        assert workflow.workflows["helper"].params == ["input"]


# =============================================================================
# Test: For loop
# =============================================================================


class TestForLoop:
    """Programmatic construction of a for loop with 'in' iteration."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="loop",
                    body=ForStep(
                        loop=ForBody(
                            value="item",
                            items=["a", "b", "c"],
                            steps=[
                                Step(
                                    name="log",
                                    body=CallStep(
                                        call="sys.log",
                                        args={"text": expr("item")},
                                    ),
                                ),
                            ],
                        )
                    ),
                ),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "for_loop.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_model_structure(self, workflow):
        step = workflow.steps[0]
        assert isinstance(step.body, ForStep)
        assert step.body.loop.value == "item"
        assert step.body.loop.items == ["a", "b", "c"]


# =============================================================================
# Test: Switch
# =============================================================================


class TestSwitch:
    """Programmatic construction of a switch step with conditions."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 10}])),
                Step(
                    name="check",
                    body=SwitchStep(
                        switch=[
                            SwitchCondition(condition=expr("x > 0"), next="positive"),
                            SwitchCondition(condition=True, next="negative"),
                        ]
                    ),
                ),
                Step(name="positive", body=ReturnStep(returns="positive")),
                Step(name="negative", body=ReturnStep(returns="negative")),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "switch.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Parallel branches
# =============================================================================


class TestParallelBranches:
    """Programmatic construction of parallel branches."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="parallel_work",
                    body=ParallelStep(
                        parallel=ParallelBody(
                            branches=[
                                Branch(
                                    name="branch1",
                                    steps=[
                                        Step(
                                            name="b1_step",
                                            body=CallStep(
                                                call="sys.log",
                                                args={"text": "branch1"},
                                            ),
                                        ),
                                    ],
                                ),
                                Branch(
                                    name="branch2",
                                    steps=[
                                        Step(
                                            name="b2_step",
                                            body=CallStep(
                                                call="sys.log",
                                                args={"text": "branch2"},
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ),
                ),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "parallel_branches.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Try/except/retry
# =============================================================================


class TestTryExceptRetry:
    """Programmatic construction of try/except with custom retry config."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="try_call",
                    body=TryStep(
                        steps=TryCallBody(
                            call="http.get",
                            args={"url": "https://example.com"},
                            result="response",
                        ),
                        retry=RetryConfig(
                            predicate=expr("e.code == 429"),
                            max_retries=3,
                            backoff=BackoffConfig(
                                initial_delay=1, max_delay=30, multiplier=2
                            ),
                        ),
                        error_steps=ExceptBody(
                            alias="e",
                            steps=[
                                Step(
                                    name="handle",
                                    body=RaiseStep(raises=expr("e")),
                                ),
                            ],
                        ),
                    ),
                ),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "try_except_retry.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Nested steps
# =============================================================================


class TestNestedSteps:
    """Programmatic construction of nested steps with next jump."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="group",
                    body=NestedStepsStep(
                        steps=[
                            Step(
                                name="step_a",
                                body=CallStep(call="sys.log", args={"text": "a"}),
                            ),
                            Step(
                                name="step_b",
                                body=CallStep(call="sys.log", args={"text": "b"}),
                            ),
                        ],
                        next="done",
                    ),
                ),
                Step(name="done", body=ReturnStep(returns="ok")),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "nested_steps.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Module-level to_yaml() helper
# =============================================================================


class TestToYamlHelper:
    """Test the standalone to_yaml() function dispatches correctly."""

    def test_simple_workflow(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="done", body=ReturnStep(returns="ok")),
            ]
        )
        result = to_yaml(w)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, list)
        assert "done" in parsed[0]

    def test_subworkflows_workflow(self):
        w = SubworkflowsWorkflow(
            workflows={
                "main": WorkflowDefinition(
                    steps=[
                        Step(name="done", body=ReturnStep(returns="ok")),
                    ]
                ),
            }
        )
        result = to_yaml(w)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert "main" in parsed

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            to_yaml("not a workflow")


# =============================================================================
# Test: expr() helper
# =============================================================================


class TestExprHelper:
    """Test the expr() helper for building ${...} expressions."""

    def test_basic_expression(self):
        assert expr("x + y") == "${x + y}"

    def test_nested_braces(self):
        assert expr('map.get("key")') == '${map.get("key")}'

    def test_empty_body(self):
        assert expr("") == "${}"

    def test_used_in_workflow(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 10}])),
                Step(name="done", body=ReturnStep(returns=expr("x"))),
            ]
        )
        result = w.to_dict()
        assert result[1]["done"]["return"] == "${x}"


# =============================================================================
# Test: analyze_workflow() direct validation
# =============================================================================


class TestAnalyzeWorkflow:
    """Test analyze_workflow() validates without YAML round-trip."""

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            analyze_workflow("not a workflow")


# =============================================================================
# Test: Try with steps body (Form B)
# =============================================================================


class TestTryWithStepsBody:
    """Try step with a steps block instead of a single call."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="try_steps",
                    body=TryStep(
                        steps=TryStepsBody(
                            steps=[
                                Step(
                                    name="step1",
                                    body=CallStep(
                                        call="sys.log", args={"text": "hello"}
                                    ),
                                ),
                                Step(
                                    name="step2",
                                    body=CallStep(
                                        call="sys.log", args={"text": "world"}
                                    ),
                                ),
                            ]
                        ),
                        error_steps=ExceptBody(
                            alias="e",
                            steps=[
                                Step(name="handle", body=ReturnStep(returns="error")),
                            ],
                        ),
                    ),
                ),
            ]
        )

    def test_serializes_correctly(self, workflow):
        result = workflow.to_dict()
        try_body = result[0]["try_steps"]["try"]
        assert "steps" in try_body
        assert len(try_body["steps"]) == 2

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: CDK edge cases (merged from small 2-test classes)
# =============================================================================


class TestCdkEdgeCases:
    """Edge cases: call/assign with next, for with range, parallel for,
    switch with embedded actions, raise step."""

    # -- Call with next --

    def test_call_next_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="do_call",
                    body=CallStep(
                        call="sys.log",
                        args={"text": "hello"},
                        next="final",
                    ),
                ),
                Step(name="skipped", body=ReturnStep(returns="skipped")),
                Step(name="final", body=ReturnStep(returns="done")),
            ]
        )
        result = w.to_dict()
        assert result[0]["do_call"]["next"] == "final"

    def test_call_next_passes_analysis(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="do_call",
                    body=CallStep(
                        call="sys.log",
                        args={"text": "hello"},
                        next="final",
                    ),
                ),
                Step(name="skipped", body=ReturnStep(returns="skipped")),
                Step(name="final", body=ReturnStep(returns="done")),
            ]
        )
        assert_passes_analysis(w)

    # -- Assign with next --

    def test_assign_next_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="init",
                    body=AssignStep(assign=[{"x": 1}], next="end"),
                ),
                Step(name="skipped", body=ReturnStep(returns="skipped")),
                Step(name="end", body=ReturnStep(returns=expr("x"))),
            ]
        )
        result = w.to_dict()
        assert result[0]["init"]["next"] == "end"

    def test_assign_next_passes_analysis(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="init",
                    body=AssignStep(assign=[{"x": 1}], next="end"),
                ),
                Step(name="skipped", body=ReturnStep(returns="skipped")),
                Step(name="end", body=ReturnStep(returns=expr("x"))),
            ]
        )
        assert_passes_analysis(w)

    # -- For with range --

    def test_for_range_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="count",
                    body=ForStep(
                        loop=ForBody(
                            value="i",
                            range=[1, 10],
                            steps=[
                                Step(
                                    name="log",
                                    body=CallStep(
                                        call="sys.log", args={"text": expr("i")}
                                    ),
                                ),
                            ],
                        )
                    ),
                ),
            ]
        )
        result = w.to_dict()
        for_body = result[0]["count"]["for"]
        assert for_body["range"] == [1, 10]
        assert "in" not in for_body

    def test_for_range_passes_analysis(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="count",
                    body=ForStep(
                        loop=ForBody(
                            value="i",
                            range=[1, 10],
                            steps=[
                                Step(
                                    name="log",
                                    body=CallStep(
                                        call="sys.log", args={"text": expr("i")}
                                    ),
                                ),
                            ],
                        )
                    ),
                ),
            ]
        )
        assert_passes_analysis(w)

    # -- Parallel for --

    def test_parallel_for_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="parallel_loop",
                    body=ParallelStep(
                        parallel=ParallelBody(
                            shared=["results"],
                            loop=ForBody(
                                value="item",
                                items=["a", "b", "c"],
                                steps=[
                                    Step(
                                        name="process",
                                        body=CallStep(
                                            call="sys.log",
                                            args={"text": expr("item")},
                                        ),
                                    ),
                                ],
                            ),
                        )
                    ),
                ),
            ]
        )
        result = w.to_dict()
        parallel = result[0]["parallel_loop"]["parallel"]
        assert "for" in parallel
        assert parallel["shared"] == ["results"]
        assert "branches" not in parallel

    def test_parallel_for_passes_analysis(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="parallel_loop",
                    body=ParallelStep(
                        parallel=ParallelBody(
                            shared=["results"],
                            loop=ForBody(
                                value="item",
                                items=["a", "b", "c"],
                                steps=[
                                    Step(
                                        name="process",
                                        body=CallStep(
                                            call="sys.log",
                                            args={"text": expr("item")},
                                        ),
                                    ),
                                ],
                            ),
                        )
                    ),
                ),
            ]
        )
        assert_passes_analysis(w)

    # -- Switch with embedded return --

    def test_switch_embedded_return_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 5}])),
                Step(
                    name="decide",
                    body=SwitchStep(
                        switch=[
                            SwitchCondition(
                                condition=expr("x > 0"), returns="positive"
                            ),
                            SwitchCondition(condition=True, returns="non-positive"),
                        ]
                    ),
                ),
            ]
        )
        result = w.to_dict()
        conditions = result[1]["decide"]["switch"]
        assert conditions[0]["return"] == "positive"
        assert conditions[1]["return"] == "non-positive"

    def test_switch_embedded_return_passes_analysis(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 5}])),
                Step(
                    name="decide",
                    body=SwitchStep(
                        switch=[
                            SwitchCondition(
                                condition=expr("x > 0"), returns="positive"
                            ),
                            SwitchCondition(condition=True, returns="non-positive"),
                        ]
                    ),
                ),
            ]
        )
        assert_passes_analysis(w)

    # -- Raise step --

    def test_raise_serialized(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="fail", body=RaiseStep(raises="Something went wrong")),
            ]
        )
        result = w.to_dict()
        assert result[0]["fail"]["raise"] == "Something went wrong"

    def test_raise_with_expression(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="fail", body=RaiseStep(raises=expr("error_msg"))),
            ]
        )
        result = w.to_dict()
        assert result[0]["fail"]["raise"] == "${error_msg}"


# =============================================================================
# Test: WorkflowDefinition with default params
# =============================================================================


class TestWorkflowDefinitionParams:
    """Subworkflow params with default values."""

    @pytest.fixture
    def workflow(self):
        return SubworkflowsWorkflow(
            workflows={
                "main": WorkflowDefinition(
                    steps=[
                        Step(
                            name="call_sub",
                            body=CallStep(call="my_sub", result="res"),
                        ),
                        Step(name="done", body=ReturnStep(returns=expr("res"))),
                    ]
                ),
                "my_sub": WorkflowDefinition(
                    params=["required_param", {"optional_param": "default_val"}],
                    steps=[
                        Step(name="done", body=ReturnStep(returns="ok")),
                    ],
                ),
            }
        )

    def test_params_serialized(self, workflow):
        result = workflow.to_dict()
        params = result["my_sub"]["params"]
        assert params[0] == "required_param"
        assert params[1] == {"optional_param": "default_val"}

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)
