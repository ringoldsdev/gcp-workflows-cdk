"""Pydantic v2 models for Google Cloud Workflows YAML validation.

Follows the specification in docs/06_pydantic_design.md exactly.
Models are defined in dependency order (leaf-first), with forward references
resolved via model_rebuild() at module end.

Serialization uses Pydantic's native model_dump(by_alias=True, exclude_none=True).
Step and Branch use @model_serializer to reverse their structural transforms.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union, Annotated

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    field_validator,
    model_serializer,
    model_validator,
)


# =============================================================================
# Helper functions
# =============================================================================


def expr(body: str) -> str:
    """Wrap an expression body in ${...} syntax."""
    return f"${{{body}}}"


def _to_expr_fragment(value: Any) -> str:
    """Convert a Python value to a GCP Workflows expression fragment.

    - Strings wrapped in ${...} are unwrapped to their expression body.
    - Plain strings are quoted as string literals.
    - Numbers (int, float) are converted to their string representation.
    - Booleans become ``true`` / ``false``.
    - ``None`` becomes ``null``.
    """
    if isinstance(value, str):
        if value.startswith("${") and value.endswith("}"):
            return value[2:-1]
        # Escape backslashes and double quotes inside the string
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    raise TypeError(
        f"concat() items must be str, int, float, bool, or None — got {type(value).__name__}"
    )


def concat(items: list, separator: str = "") -> str:
    """Build a GCP Workflows ``+`` concatenation expression.

    Each item is converted to an expression fragment:

    - ``expr("var")`` (i.e. ``"${var}"``) is unwrapped to ``var``
    - Plain strings become quoted literals: ``"hello"``
    - Numbers, booleans, and ``None`` become their GCP literal form

    The *separator* is always treated as a string literal and is
    interleaved between items with ``+``.

    Returns a ``${...}`` wrapped expression string.

    Examples::

        concat(["Hello", expr("name")], " ")
        # => '${"Hello" + " " + name}'

        concat([expr("a"), expr("b"), expr("c")], ", ")
        # => '${a + ", " + b + ", " + c}'
    """
    if not items:
        return expr('""')

    fragments = [_to_expr_fragment(item) for item in items]

    if separator:
        escaped_sep = separator.replace("\\", "\\\\").replace('"', '\\"')
        sep_fragment = f'"{escaped_sep}"'
        interleaved = [fragments[0]]
        for frag in fragments[1:]:
            interleaved.append(sep_fragment)
            interleaved.append(frag)
        return expr(" + ".join(interleaved))

    return expr(" + ".join(fragments))


# =============================================================================
# 1. BackoffConfig (leaf model)
# =============================================================================


class BackoffConfig(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    initial_delay: Union[int, float]
    max_delay: Union[int, float]
    multiplier: Union[int, float]


# =============================================================================
# 2. RetryConfig
# =============================================================================


class RetryConfig(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    predicate: str  # expression or subworkflow reference
    max_retries: int = Field(..., gt=0)
    backoff: Optional[BackoffConfig] = None


# =============================================================================
# 3. ExceptBody (forward ref to Step)
# =============================================================================


class ExceptBody(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    as_: str = Field(..., alias="as")
    steps: List[Step]


# =============================================================================
# 4. TryCallBody
# =============================================================================


class TryCallBody(BaseModel):
    """Try body Form A: single call."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    call: str
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None


# =============================================================================
# 5. TryStepsBody (forward ref to Step)
# =============================================================================


class TryStepsBody(BaseModel):
    """Try body Form B: steps block."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    steps: List[Step]


# =============================================================================
# 6. SwitchCondition (forward ref to Step)
# =============================================================================


class SwitchCondition(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    condition: Any  # expression string or literal true/false
    next: Optional[str] = None
    steps: Optional[List[Step]] = None
    assign: Optional[List[Dict[str, Any]]] = None
    return_: Optional[Any] = Field(default=None, alias="return")
    raise_: Optional[Any] = Field(default=None, alias="raise")


# =============================================================================
# 6b. SwitchStep
# =============================================================================


class SwitchStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    switch: List[SwitchCondition] = Field(..., min_length=1, max_length=50)
    next: Optional[str] = Field(default=None, alias="next")


# =============================================================================
# 7. Branch (forward ref to Step)
# =============================================================================


class Branch(BaseModel):
    """A parallel branch: single-key dict {branch_name: {steps: [...]}}."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    name: str
    steps: List[Step]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError(f"Branch must be a dict, got {type(data)}")
        if "name" in data and "steps" in data:
            return data  # programmatic construction
        if len(data) != 1:
            raise ValueError("Branch must be a single-key dict")
        name, body = next(iter(data.items()))
        if not isinstance(body, dict) or "steps" not in body:
            raise ValueError(f"Branch '{name}' must have a 'steps' field")
        return {"name": name, "steps": body["steps"]}

    @model_serializer
    def _serialize(self) -> Dict[str, Any]:
        steps = [s.model_dump(by_alias=True, exclude_none=True) for s in self.steps]
        return {self.name: {"steps": steps}}


# =============================================================================
# 8. ForBody (forward ref to Step)
# =============================================================================


class ForBody(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    value: str
    index: Optional[str] = None
    in_: Optional[Any] = Field(default=None, alias="in")
    range: Optional[Any] = None
    steps: List[Step]

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> ForBody:
        has_in = self.in_ is not None
        has_range = self.range is not None
        if has_in == has_range:
            raise ValueError("Exactly one of 'in' or 'range' must be specified")
        if self.index is not None and has_range:
            raise ValueError("'index' is only valid with 'in', not 'range'")
        return self


# =============================================================================
# 9. AssignStep
# =============================================================================


class AssignStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    assign: List[Dict[str, Any]] = Field(..., min_length=1, max_length=50)
    next: Optional[str] = Field(default=None, alias="next")

    @field_validator("assign", mode="before")
    @classmethod
    def validate_assignments(cls, v: Any) -> Any:
        if not isinstance(v, list):
            raise ValueError("assign must be a list")
        for entry in v:
            if not isinstance(entry, dict):
                raise ValueError(f"Each assignment must be a dict, got {type(entry)}")
            if len(entry) != 1:
                raise ValueError("Each assignment dict must have exactly one key")
        return v


# =============================================================================
# 10. CallStep
# =============================================================================


class CallStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    call: str
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    next: Optional[str] = Field(default=None, alias="next")


# =============================================================================
# 11. ReturnStep
# =============================================================================


class ReturnStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    return_: Any = Field(..., alias="return")


# =============================================================================
# 12. RaiseStep
# =============================================================================


class RaiseStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    raise_: Any = Field(..., alias="raise")


# =============================================================================
# 13. NestedStepsStep (forward ref to Step)
# =============================================================================


class NestedStepsStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    steps: List[Step]
    next: Optional[str] = Field(default=None, alias="next")


# =============================================================================
# 14. ForStep
# =============================================================================


class ForStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    for_: ForBody = Field(..., alias="for")


# =============================================================================
# 15. ParallelBody (references ForBody, Branch)
# =============================================================================


class ParallelBody(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    exception_policy: Optional[Literal["continueAll"]] = None
    shared: Optional[List[str]] = None
    concurrency_limit: Optional[Union[int, str]] = None
    branches: Optional[List[Branch]] = None
    for_: Optional[ForBody] = Field(default=None, alias="for")

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> ParallelBody:
        has_branches = self.branches is not None
        has_for = self.for_ is not None
        if has_branches == has_for:
            raise ValueError(
                "Exactly one of 'branches' or 'for' must be specified in parallel"
            )
        if has_branches and self.branches is not None:
            if len(self.branches) < 2:
                raise ValueError("Parallel branches requires at least 2 branches")
            if len(self.branches) > 10:
                raise ValueError("Parallel branches allows at most 10 branches")
        return self


# =============================================================================
# 16. ParallelStep
# =============================================================================


class ParallelStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    parallel: ParallelBody


# =============================================================================
# 17. TryStep (references TryBody, RetryPolicy, ExceptBody)
# =============================================================================

# -- TryBody discriminator --


def try_body_discriminator(data: Any) -> str:
    if isinstance(data, TryCallBody):
        return "call"
    if isinstance(data, TryStepsBody):
        return "steps"
    if not isinstance(data, dict):
        raise ValueError("Try body must be a dict")
    if "call" in data:
        return "call"
    if "steps" in data:
        return "steps"
    raise ValueError("Try body must contain 'call' or 'steps'")


TryBody = Annotated[
    Union[
        Annotated[TryCallBody, Tag("call")],
        Annotated[TryStepsBody, Tag("steps")],
    ],
    Discriminator(try_body_discriminator),
]


# -- RetryPolicy discriminator --


def retry_discriminator(data: Any) -> str:
    if isinstance(data, str):
        return "predefined"
    if isinstance(data, (dict, RetryConfig)):
        return "custom"
    raise ValueError("Retry must be a string expression or config dict")


RetryPolicy = Annotated[
    Union[
        Annotated[str, Tag("predefined")],
        Annotated[RetryConfig, Tag("custom")],
    ],
    Discriminator(retry_discriminator),
]


class TryStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    try_: TryBody = Field(..., alias="try")
    retry: Optional[RetryPolicy] = None
    except_: Optional[ExceptBody] = Field(default=None, alias="except")


# =============================================================================
# 18. step_body_discriminator function
# =============================================================================


def step_body_discriminator(data: Any) -> str:
    """Determine step type from the keys present in the dict or model instance."""
    # Handle already-instantiated model objects (programmatic construction)
    _INSTANCE_TAG_MAP = {
        TryStep: "try",
        ParallelStep: "parallel",
        ForStep: "for",
        SwitchStep: "switch",
        CallStep: "call",
        AssignStep: "assign",
        ReturnStep: "return",
        RaiseStep: "raise",
        NestedStepsStep: "steps",
    }
    for cls, tag in _INSTANCE_TAG_MAP.items():
        if isinstance(data, cls):
            return tag
    # Handle raw dicts (YAML parsing)
    if not isinstance(data, dict):
        raise ValueError(f"Step body must be a dict, got {type(data)}")
    keys = set(data.keys())
    if "try" in keys:
        return "try"
    if "parallel" in keys:
        return "parallel"
    if "for" in keys:
        return "for"
    if "switch" in keys:
        return "switch"
    if "call" in keys:
        return "call"
    if "assign" in keys:
        return "assign"
    if "return" in keys:
        return "return"
    if "raise" in keys:
        return "raise"
    if "steps" in keys:
        return "steps"
    raise ValueError(f"Cannot determine step type from keys: {keys}")


# =============================================================================
# 19. StepBody type alias
# =============================================================================

StepBody = Annotated[
    Union[
        Annotated[TryStep, Tag("try")],
        Annotated[ParallelStep, Tag("parallel")],
        Annotated[ForStep, Tag("for")],
        Annotated[SwitchStep, Tag("switch")],
        Annotated[CallStep, Tag("call")],
        Annotated[AssignStep, Tag("assign")],
        Annotated[ReturnStep, Tag("return")],
        Annotated[RaiseStep, Tag("raise")],
        Annotated[NestedStepsStep, Tag("steps")],
    ],
    Discriminator(step_body_discriminator),
]


# =============================================================================
# 20. Step (references StepBody)
# =============================================================================


class Step(BaseModel):
    """A named step: single-key dict {step_name: step_body}."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    name: str
    body: StepBody

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError(f"Step must be a dict, got {type(data)}")
        if "name" in data and "body" in data:
            return data  # programmatic construction
        if len(data) != 1:
            raise ValueError(
                f"Step must be a single-key dict, got {len(data)} keys: {list(data.keys())}"
            )
        name, body = next(iter(data.items()))
        return {"name": name, "body": body}

    @model_serializer
    def _serialize(self) -> Dict[str, Any]:
        body_dict = self.body.model_dump(by_alias=True, exclude_none=True)
        return {self.name: body_dict}


# =============================================================================
# 21. WorkflowDefinition (references Step)
# =============================================================================


class WorkflowDefinition(BaseModel):
    """A single workflow (main or subworkflow)."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    params: Optional[List[Union[str, Dict[str, Any]]]] = None
    steps: List[Step]

    @field_validator("params", mode="before")
    @classmethod
    def validate_params(cls, v: Any) -> Any:
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("params must be a list")
        for entry in v:
            if isinstance(entry, str):
                continue
            elif isinstance(entry, dict):
                if len(entry) != 1:
                    raise ValueError("Each params dict entry must have exactly one key")
            else:
                raise ValueError(
                    f"Each params entry must be str or single-key dict, got {type(entry)}"
                )
        return v


# =============================================================================
# 22. SimpleWorkflow
# =============================================================================


class SimpleWorkflow(BaseModel):
    """Form A: top-level is a list of steps."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    steps: List[Step]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"steps": data}
        if isinstance(data, dict):
            return data
        raise ValueError("SimpleWorkflow expects a list or dict")

    def to_dict(self) -> List[Dict[str, Any]]:
        """Serialize to the YAML-compatible list-of-step-dicts format."""
        return self.model_dump(by_alias=True, exclude_none=True)["steps"]

    def to_yaml(self) -> str:
        """Serialize to a YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


# =============================================================================
# 23. SubworkflowsWorkflow
# =============================================================================


class SubworkflowsWorkflow(BaseModel):
    """Form B: top-level is a dict of workflow definitions."""

    model_config = ConfigDict(strict=False, populate_by_name=True)

    workflows: Dict[str, WorkflowDefinition]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if len(data) == 1 and "workflows" in data:
                return data  # programmatic construction
            if "main" not in data:
                raise ValueError("Form B requires a 'main' key")
            return {"workflows": data}
        raise ValueError("SubworkflowsWorkflow expects a dict")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the YAML-compatible dict-of-workflows format."""
        return self.model_dump(by_alias=True, exclude_none=True)["workflows"]

    def to_yaml(self) -> str:
        """Serialize to a YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)


# =============================================================================
# 24. Workflow union type + parse_workflow + to_yaml
# =============================================================================

Workflow = Union[SimpleWorkflow, SubworkflowsWorkflow]


def parse_workflow(yaml_str: str) -> Workflow:
    """Parse and validate a Cloud Workflows YAML string."""
    raw = yaml.safe_load(yaml_str)
    if isinstance(raw, list):
        return SimpleWorkflow.model_validate(raw)
    elif isinstance(raw, dict):
        return SubworkflowsWorkflow.model_validate(raw)
    else:
        raise ValueError("Workflow must be a list or dict")


def to_yaml(workflow: Workflow) -> str:
    """Serialize any Workflow to a YAML string."""
    if isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
        return workflow.to_yaml()
    raise TypeError(
        f"Expected SimpleWorkflow or SubworkflowsWorkflow, got {type(workflow)}"
    )


# =============================================================================
# 25. Forward reference rebuilds
# =============================================================================

Step.model_rebuild()
SwitchCondition.model_rebuild()
ForBody.model_rebuild()
NestedStepsStep.model_rebuild()
TryStepsBody.model_rebuild()
Branch.model_rebuild()
ExceptBody.model_rebuild()
ParallelBody.model_rebuild()
WorkflowDefinition.model_rebuild()
SimpleWorkflow.model_rebuild()
