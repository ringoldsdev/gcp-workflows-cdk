"""Tests for programmatic workflow construction and serialization (CDK layer).

Each test constructs a workflow programmatically using the Pydantic model classes,
serializes via to_yaml()/to_dict(), and verifies:
  - YAML output matches the corresponding fixture file
  - analyze_yaml() on the serialized YAML passes all 3 validation stages
  - analyze_workflow() on the model directly passes all 3 validation stages
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
                Step(name="done", body=ReturnStep(return_=expr("x + y"))),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "simple_assign.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_to_dict_returns_list(self, workflow):
        result = workflow.to_dict()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_to_dict_step_names(self, workflow):
        result = workflow.to_dict()
        assert "init" in result[0]
        assert "done" in result[1]

    def test_to_dict_assign_values(self, workflow):
        result = workflow.to_dict()
        assign_body = result[0]["init"]["assign"]
        assert assign_body == [{"x": 10}, {"y": 20}]

    def test_to_dict_return_expression(self, workflow):
        result = workflow.to_dict()
        return_body = result[1]["done"]["return"]
        assert return_body == "${x + y}"

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
                        Step(name="done", body=ReturnStep(return_=expr("res"))),
                    ]
                ),
                "helper": WorkflowDefinition(
                    params=["input"],
                    steps=[
                        Step(
                            name="log",
                            body=CallStep(call="sys.log", args={"text": expr("input")}),
                        ),
                        Step(name="done", body=ReturnStep(return_="ok")),
                    ],
                ),
            }
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "subworkflows.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_to_dict_returns_dict(self, workflow):
        result = workflow.to_dict()
        assert isinstance(result, dict)
        assert "main" in result
        assert "helper" in result

    def test_to_dict_main_has_steps(self, workflow):
        result = workflow.to_dict()
        assert "steps" in result["main"]
        assert len(result["main"]["steps"]) == 2

    def test_to_dict_helper_has_params(self, workflow):
        result = workflow.to_dict()
        assert result["helper"]["params"] == ["input"]

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
                        for_=ForBody(
                            value="item",
                            in_=["a", "b", "c"],
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

    def test_to_dict_for_body(self, workflow):
        result = workflow.to_dict()
        for_body = result[0]["loop"]["for"]
        assert for_body["value"] == "item"
        assert for_body["in"] == ["a", "b", "c"]
        assert "steps" in for_body

    def test_model_structure(self, workflow):
        step = workflow.steps[0]
        assert isinstance(step.body, ForStep)
        assert step.body.for_.value == "item"
        assert step.body.for_.in_ == ["a", "b", "c"]


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
                Step(name="positive", body=ReturnStep(return_="positive")),
                Step(name="negative", body=ReturnStep(return_="negative")),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "switch.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_to_dict_switch_conditions(self, workflow):
        result = workflow.to_dict()
        switch_body = result[1]["check"]["switch"]
        assert len(switch_body) == 2
        assert switch_body[0]["condition"] == "${x > 0}"
        assert switch_body[0]["next"] == "positive"
        assert switch_body[1]["condition"] is True
        assert switch_body[1]["next"] == "negative"


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

    def test_to_dict_branches(self, workflow):
        result = workflow.to_dict()
        parallel = result[0]["parallel_work"]["parallel"]
        branches = parallel["branches"]
        assert len(branches) == 2
        assert "branch1" in branches[0]
        assert "branch2" in branches[1]


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
                        try_=TryCallBody(
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
                        except_=ExceptBody(
                            as_="e",
                            steps=[
                                Step(
                                    name="handle",
                                    body=RaiseStep(raise_=expr("e")),
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

    def test_to_dict_try_structure(self, workflow):
        result = workflow.to_dict()
        try_body = result[0]["try_call"]
        assert "try" in try_body
        assert try_body["try"]["call"] == "http.get"
        assert try_body["try"]["result"] == "response"

    def test_to_dict_retry_config(self, workflow):
        result = workflow.to_dict()
        retry = result[0]["try_call"]["retry"]
        assert retry["predicate"] == "${e.code == 429}"
        assert retry["max_retries"] == 3
        assert retry["backoff"]["initial_delay"] == 1

    def test_to_dict_except_body(self, workflow):
        result = workflow.to_dict()
        except_body = result[0]["try_call"]["except"]
        assert except_body["as"] == "e"
        assert len(except_body["steps"]) == 1


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
                Step(name="done", body=ReturnStep(return_="ok")),
            ]
        )

    def test_yaml_matches_fixture(self, workflow):
        assert_yaml_matches_fixture(workflow, "cdk", "nested_steps.yaml")

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)

    def test_to_dict_nested_structure(self, workflow):
        result = workflow.to_dict()
        group = result[0]["group"]
        assert "steps" in group
        assert len(group["steps"]) == 2
        assert group["next"] == "done"


# =============================================================================
# Test: Module-level to_yaml() helper
# =============================================================================


class TestToYamlHelper:
    """Test the standalone to_yaml() function dispatches correctly."""

    def test_simple_workflow(self):
        w = SimpleWorkflow(
            steps=[
                Step(name="done", body=ReturnStep(return_="ok")),
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
                        Step(name="done", body=ReturnStep(return_="ok")),
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
                Step(name="done", body=ReturnStep(return_=expr("x"))),
            ]
        )
        result = w.to_dict()
        assert result[1]["done"]["return"] == "${x}"


# =============================================================================
# Test: Dict-level round-trip (parse fixture → to_dict → compare)
# =============================================================================


class TestDictRoundTrip:
    """Parse existing YAML fixtures, serialize back via to_dict(), and verify equivalence."""

    def _round_trip(self, *fixture_path_parts):
        """Load fixture, parse it, serialize to dict, compare to original."""
        yaml_str = load_fixture(*fixture_path_parts)
        original = yaml.safe_load(yaml_str)

        # Parse fixture into a model
        wf = parse_fixture(*fixture_path_parts)

        # Serialize back to dict
        serialized = wf.to_dict()
        assert serialized == original, (
            f"Round-trip mismatch for {'/'.join(fixture_path_parts)}:\n"
            f"  original:   {original}\n"
            f"  serialized: {serialized}"
        )

    def test_simple_assign(self):
        self._round_trip("cdk", "simple_assign.yaml")

    def test_subworkflows(self):
        self._round_trip("cdk", "subworkflows.yaml")

    def test_for_loop(self):
        self._round_trip("cdk", "for_loop.yaml")

    def test_switch(self):
        self._round_trip("cdk", "switch.yaml")

    def test_parallel_branches(self):
        self._round_trip("cdk", "parallel_branches.yaml")

    def test_try_except_retry(self):
        self._round_trip("cdk", "try_except_retry.yaml")

    def test_nested_steps(self):
        self._round_trip("cdk", "nested_steps.yaml")


# =============================================================================
# Test: analyze_workflow() direct validation
# =============================================================================


class TestAnalyzeWorkflow:
    """Test analyze_workflow() validates without YAML round-trip."""

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            analyze_workflow("not a workflow")


# =============================================================================
# Test: Validation errors on invalid programmatic construction
# =============================================================================

from pydantic import ValidationError


class TestConstructionValidation:
    """Pydantic validates constraints during programmatic construction."""

    def test_assign_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            AssignStep(assign=[])

    def test_assign_multi_key_dict_rejected(self):
        with pytest.raises(ValidationError):
            AssignStep(assign=[{"a": 1, "b": 2}])

    def test_for_both_in_and_range_rejected(self):
        with pytest.raises(ValidationError):
            ForBody(
                value="x",
                in_=[1, 2],
                range=[1, 10],
                steps=[Step(name="s", body=ReturnStep(return_="ok"))],
            )

    def test_for_neither_in_nor_range_rejected(self):
        with pytest.raises(ValidationError):
            ForBody(
                value="x",
                steps=[Step(name="s", body=ReturnStep(return_="ok"))],
            )

    def test_parallel_fewer_than_2_branches_rejected(self):
        with pytest.raises(ValidationError):
            ParallelBody(
                branches=[
                    Branch(
                        name="only_one",
                        steps=[
                            Step(name="s", body=ReturnStep(return_="ok")),
                        ],
                    ),
                ]
            )

    def test_switch_empty_conditions_rejected(self):
        with pytest.raises(ValidationError):
            SwitchStep(switch=[])

    def test_retry_zero_max_retries_rejected(self):
        with pytest.raises(ValidationError):
            RetryConfig(
                predicate="${true}",
                max_retries=0,
                backoff=BackoffConfig(initial_delay=1, max_delay=10, multiplier=2),
            )


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
                        try_=TryStepsBody(
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
                        except_=ExceptBody(
                            as_="e",
                            steps=[
                                Step(name="handle", body=ReturnStep(return_="error")),
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
# Test: Call step with next
# =============================================================================


class TestCallWithNext:
    """Call step using the next field for flow control."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="do_call",
                    body=CallStep(
                        call="sys.log",
                        args={"text": "hello"},
                        next="final",
                    ),
                ),
                Step(name="skipped", body=ReturnStep(return_="skipped")),
                Step(name="final", body=ReturnStep(return_="done")),
            ]
        )

    def test_next_serialized(self, workflow):
        result = workflow.to_dict()
        call_body = result[0]["do_call"]
        assert call_body["next"] == "final"

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Assign step with next
# =============================================================================


class TestAssignWithNext:
    """Assign step using the next field for flow control."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="init",
                    body=AssignStep(
                        assign=[{"x": 1}],
                        next="end",
                    ),
                ),
                Step(name="skipped", body=ReturnStep(return_="skipped")),
                Step(name="end", body=ReturnStep(return_=expr("x"))),
            ]
        )

    def test_next_serialized(self, workflow):
        result = workflow.to_dict()
        assign_body = result[0]["init"]
        assert assign_body["next"] == "end"

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: For loop with range
# =============================================================================


class TestForRange:
    """For loop with range instead of 'in'."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="count",
                    body=ForStep(
                        for_=ForBody(
                            value="i",
                            range=[1, 10],
                            steps=[
                                Step(
                                    name="log",
                                    body=CallStep(
                                        call="sys.log",
                                        args={"text": expr("i")},
                                    ),
                                ),
                            ],
                        )
                    ),
                ),
            ]
        )

    def test_serializes_with_range(self, workflow):
        result = workflow.to_dict()
        for_body = result[0]["count"]["for"]
        assert for_body["range"] == [1, 10]
        assert "in" not in for_body

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Parallel for
# =============================================================================


class TestParallelFor:
    """Parallel step with a for loop instead of branches."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="parallel_loop",
                    body=ParallelStep(
                        parallel=ParallelBody(
                            shared=["results"],
                            for_=ForBody(
                                value="item",
                                in_=["a", "b", "c"],
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

    def test_serializes_with_for(self, workflow):
        result = workflow.to_dict()
        parallel = result[0]["parallel_loop"]["parallel"]
        assert "for" in parallel
        assert parallel["shared"] == ["results"]
        assert "branches" not in parallel

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Switch with embedded assign and return
# =============================================================================


class TestSwitchWithEmbeddedActions:
    """Switch conditions with embedded assign and return actions."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(name="init", body=AssignStep(assign=[{"x": 5}])),
                Step(
                    name="decide",
                    body=SwitchStep(
                        switch=[
                            SwitchCondition(
                                condition=expr("x > 0"),
                                return_="positive",
                            ),
                            SwitchCondition(
                                condition=True,
                                return_="non-positive",
                            ),
                        ]
                    ),
                ),
            ]
        )

    def test_serializes_return_in_condition(self, workflow):
        result = workflow.to_dict()
        conditions = result[1]["decide"]["switch"]
        assert conditions[0]["return"] == "positive"
        assert conditions[1]["return"] == "non-positive"

    def test_passes_analysis(self, workflow):
        assert_passes_analysis(workflow)


# =============================================================================
# Test: Raise step
# =============================================================================


class TestRaiseStep:
    """Programmatic construction with a raise step."""

    @pytest.fixture
    def workflow(self):
        return SimpleWorkflow(
            steps=[
                Step(
                    name="fail",
                    body=RaiseStep(raise_="Something went wrong"),
                ),
            ]
        )

    def test_serializes_raise(self, workflow):
        result = workflow.to_dict()
        assert result[0]["fail"]["raise"] == "Something went wrong"

    def test_raise_with_expression(self):
        w = SimpleWorkflow(
            steps=[
                Step(
                    name="fail",
                    body=RaiseStep(raise_=expr("error_msg")),
                ),
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
                        Step(name="done", body=ReturnStep(return_=expr("res"))),
                    ]
                ),
                "my_sub": WorkflowDefinition(
                    params=["required_param", {"optional_param": "default_val"}],
                    steps=[
                        Step(name="done", body=ReturnStep(return_="ok")),
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
