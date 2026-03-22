"""Fluent builder API for constructing Cloud Workflows programmatically.

Supports chaining .step() calls with either Pydantic model instances or
plain dicts. TypedDict definitions provide IDE autocompletion for dict-based
construction.

Usage:
    from cloud_workflows import WorkflowBuilder, AssignStep, ReturnStep, expr

    # Simple workflow with model instances:
    w = (WorkflowBuilder()
        .step("init", AssignStep(assign=[{"x": 1}]))
        .step("done", ReturnStep(return_="${x}"))
        .build())

    # Simple workflow with dicts (IDE-hinted):
    w = (WorkflowBuilder()
        .step("init", {"assign": [{"x": 1}]})
        .step("done", {"return": "${x}"})
        .build())

    # Subworkflows:
    w = (WorkflowBuilder()
        .workflow("main")
            .step("call_it", {"call": "helper", "args": {"n": 1}})
        .workflow("helper", params=["n"])
            .step("done", {"return": "${n}"})
        .build())
"""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Union,
    cast,
)
from typing_extensions import NotRequired, TypedDict

from .models import (
    AssignStep,
    CallStep,
    ForStep,
    NestedStepsStep,
    ParallelStep,
    RaiseStep,
    ReturnStep,
    SimpleWorkflow,
    Step,
    SubworkflowsWorkflow,
    SwitchStep,
    TryStep,
    WorkflowDefinition,
)

__all__ = [
    "WorkflowBuilder",
    "AssignDict",
    "CallDict",
    "ReturnDict",
    "RaiseDict",
    "SwitchConditionDict",
    "SwitchDict",
    "ForBodyDict",
    "ForDict",
    "ParallelBodyDict",
    "ParallelDict",
    "TryDict",
    "NestedStepsDict",
    "BackoffConfigDict",
    "RetryConfigDict",
    "StepBodyInput",
]


# =============================================================================
# TypedDict definitions for dict-based step construction
# =============================================================================
#
# These mirror the Pydantic model fields but use the YAML alias names
# (e.g. "return" not "return_") since that's what you'd write in a dict.
# NotRequired marks optional fields.
#
# TypedDicts whose keys include Python reserved words ("return", "raise",
# "for", "try", "except", "as", "in") must use the functional syntax.
# =============================================================================


class AssignDict(TypedDict):
    """Dict form of AssignStep."""

    assign: List[Dict[str, Any]]
    next: NotRequired[str]


class CallDict(TypedDict):
    """Dict form of CallStep."""

    call: str
    args: NotRequired[Dict[str, Any]]
    result: NotRequired[str]
    next: NotRequired[str]


# "return" is a reserved word — must use functional syntax
ReturnDict = TypedDict("ReturnDict", {"return": Any})
"""Dict form of ReturnStep."""

# "raise" is a reserved word — must use functional syntax
RaiseDict = TypedDict("RaiseDict", {"raise": Any})
"""Dict form of RaiseStep."""


class SwitchConditionDict(TypedDict):
    """Dict form of SwitchCondition.

    Note: "return" and "raise" keys can be passed in the dict — Pydantic
    accepts them — but they can't appear in this TypedDict definition due
    to Python's reserved word restriction in class syntax.
    """

    condition: Any
    next: NotRequired[str]
    steps: NotRequired[List[Dict[str, Any]]]
    assign: NotRequired[List[Dict[str, Any]]]


class SwitchDict(TypedDict):
    """Dict form of SwitchStep."""

    switch: List[SwitchConditionDict]
    next: NotRequired[str]


# "in" is a reserved word — must use functional syntax
ForBodyDict = TypedDict(
    "ForBodyDict",
    {
        "value": str,
        "index": NotRequired[str],
        "in": NotRequired[Any],
        "range": NotRequired[Any],
        "steps": List[Dict[str, Any]],
    },
)
"""Dict form of ForBody."""

# "for" is a reserved word — must use functional syntax
ForDict = TypedDict("ForDict", {"for": ForBodyDict})
"""Dict form of ForStep."""


class BackoffConfigDict(TypedDict):
    """Dict form of BackoffConfig."""

    initial_delay: Union[int, float]
    max_delay: Union[int, float]
    multiplier: Union[int, float]


class RetryConfigDict(TypedDict):
    """Dict form of RetryConfig."""

    predicate: str
    max_retries: int
    backoff: BackoffConfigDict


class ParallelBodyDict(TypedDict):
    """Dict form of ParallelBody.

    Note: the "for" key can be passed in the dict — Pydantic accepts it —
    but it can't appear in this TypedDict definition.
    """

    exception_policy: NotRequired[Literal["continueAll"]]
    shared: NotRequired[List[str]]
    concurrency_limit: NotRequired[Union[int, str]]
    branches: NotRequired[List[Dict[str, Any]]]


class ParallelDict(TypedDict):
    """Dict form of ParallelStep."""

    parallel: ParallelBodyDict


# "try" and "except" are reserved words — must use functional syntax
TryDict = TypedDict(
    "TryDict",
    {
        "try": Dict[str, Any],
        "retry": NotRequired[Union[str, RetryConfigDict]],
        "except": NotRequired[Dict[str, Any]],
    },
)
"""Dict form of TryStep."""


class NestedStepsDict(TypedDict):
    """Dict form of NestedStepsStep."""

    steps: List[Dict[str, Any]]
    next: NotRequired[str]


# The union type for .step() second parameter.
# IDEs will offer completions from all these types.
StepBodyInput = Union[
    # Pydantic model instances
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SwitchStep,
    ForStep,
    ParallelStep,
    TryStep,
    NestedStepsStep,
    # TypedDict hints for plain dicts
    AssignDict,
    CallDict,
    ReturnDict,
    RaiseDict,
    SwitchDict,
    ForDict,
    ParallelDict,
    TryDict,
    NestedStepsDict,
    # Fallback for dicts that don't match a specific TypedDict
    Dict[str, Any],
]


# =============================================================================
# WorkflowBuilder
# =============================================================================


class WorkflowBuilder:
    """Fluent builder for constructing workflows via .step() chaining.

    Two modes:
    - Simple workflow: just call .step() directly, then .build()
    - Subworkflows: call .workflow("name") to start each subworkflow, then .step()

    .build() returns a SimpleWorkflow or SubworkflowsWorkflow depending on
    whether .workflow() was ever called.
    """

    def __init__(self) -> None:
        self._steps: List[Step] = []
        self._workflows: Dict[
            str, tuple[Optional[List[Union[str, Dict[str, Any]]]], List[Step]]
        ] = {}
        self._current_workflow: Optional[str] = None
        self._is_subworkflow_mode: bool = False

    def step(self, name: str, body: StepBodyInput) -> WorkflowBuilder:
        """Add a step. `body` can be a Pydantic model or a dict.

        Args:
            name: Step identifier (unique within the workflow/subworkflow).
            body: Step body — a Pydantic model instance (e.g. AssignStep(...))
                  or a plain dict (e.g. {"assign": [{"x": 1}]}).

        Returns:
            self, for chaining.
        """
        # cast() satisfies the type checker — at runtime, Step's model_validator
        # accepts both Pydantic model instances and plain dicts.
        step = Step(name=name, body=cast(Any, body))

        if self._is_subworkflow_mode:
            if self._current_workflow is None:
                raise ValueError(
                    "Call .workflow('name') before .step() in subworkflow mode"
                )
            self._workflows[self._current_workflow][1].append(step)
        else:
            self._steps.append(step)

        return self

    def workflow(
        self,
        name: str,
        params: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> WorkflowBuilder:
        """Start a new subworkflow definition.

        The first call to .workflow() switches the builder to subworkflow mode.
        Subsequent .step() calls add steps to this subworkflow until the next
        .workflow() call.

        Args:
            name: Subworkflow name (e.g. "main", "helper").
            params: Optional parameter list for the subworkflow.

        Returns:
            self, for chaining.
        """
        if self._steps and not self._is_subworkflow_mode:
            raise ValueError(
                "Cannot mix .step() and .workflow() — "
                "call .workflow() before any .step() calls, "
                "or use only .step() for a simple workflow"
            )

        self._is_subworkflow_mode = True

        if name in self._workflows:
            raise ValueError(f"Duplicate workflow name: '{name}'")

        self._workflows[name] = (params, [])
        self._current_workflow = name

        return self

    def build(self) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Finalize and return the constructed workflow.

        Returns:
            SimpleWorkflow if only .step() was used.
            SubworkflowsWorkflow if .workflow() was used.

        Raises:
            ValueError: If no steps were added, or if a subworkflow has no steps.
        """
        if self._is_subworkflow_mode:
            if not self._workflows:
                raise ValueError("No workflows defined — call .workflow() first")

            workflows: Dict[str, WorkflowDefinition] = {}
            for wf_name, (wf_params, wf_steps) in self._workflows.items():
                if not wf_steps:
                    raise ValueError(
                        f"Workflow '{wf_name}' has no steps — add at least one .step()"
                    )
                workflows[wf_name] = WorkflowDefinition(
                    params=wf_params,
                    steps=wf_steps,
                )

            return SubworkflowsWorkflow(workflows=workflows)
        else:
            if not self._steps:
                raise ValueError("No steps added — call .step() first")

            return SimpleWorkflow(steps=self._steps)
