# Pydantic v2 Model Design Specification

> **THE IMPLEMENTATION BLUEPRINT.** This document specifies exactly which Pydantic v2
> classes to create, their fields, validators, and relationships. A fresh session should
> be able to implement `models.py` by following this spec line-by-line.
>
> **Target**: Single file `src/cloud_workflows/models.py`
> **Dependencies**: `pydantic>=2.0`, `pyyaml>=6.0`

---

## 0. Design Principles

1. **Single file**: All models in one `models.py` file.
2. **Strict from the start**: Enforce all documented constraints (max limits, mutual
   exclusivity, required fields).
3. **Use Pydantic v2 API**: `BaseModel`, `model_validator`, `field_validator`,
   `ConfigDict`, `Field`, `Annotated`, `Discriminator`.
4. **Forward references**: Use string annotations where needed for recursive types.
   Call `model_rebuild()` at module end for recursive models.
5. **Any for values**: Use `Any` for expression values, return values, raise values,
   assign right-hand sides, and call args values.
6. **Parsing strategy**: Load YAML first with PyYAML, then validate the resulting Python
   dict/list through Pydantic models.

---

## 1. Module Structure

```python
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from annotated_types import MinLen, MaxLen
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
```

---

## 2. Top-Level Root Model

### `parse_workflow(yaml_str: str) -> Workflow`

A standalone function (not a model) that:
1. Calls `yaml.safe_load(yaml_str)` to get raw data
2. Determines Form A vs Form B
3. Validates through the appropriate model

### `Workflow` (Union type)

```python
Workflow = Union[SimpleWorkflow, SubworkflowsWorkflow]
```

### `SimpleWorkflow`

For Form A (flat list of steps, no subworkflows):

```python
class SimpleWorkflow(BaseModel):
    """Form A: top-level is a list of steps."""
    model_config = ConfigDict(strict=False)

    steps: List[Step]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"steps": data}
        raise ValueError("SimpleWorkflow expects a list")
```

### `SubworkflowsWorkflow`

For Form B (dict with `main` + optional subworkflows):

```python
class SubworkflowsWorkflow(BaseModel):
    """Form B: top-level is a dict of workflow definitions."""
    model_config = ConfigDict(strict=False)

    workflows: Dict[str, WorkflowDefinition]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "main" not in data:
                raise ValueError("Form B requires a 'main' key")
            return {"workflows": data}
        raise ValueError("SubworkflowsWorkflow expects a dict")
```

### Parsing Logic

```python
def parse_workflow(yaml_str: str) -> Workflow:
    raw = yaml.safe_load(yaml_str)
    if isinstance(raw, list):
        return SimpleWorkflow.model_validate(raw)
    elif isinstance(raw, dict):
        return SubworkflowsWorkflow.model_validate(raw)
    else:
        raise ValueError("Workflow must be a list or dict")
```

---

## 3. WorkflowDefinition

```python
class WorkflowDefinition(BaseModel):
    """A single workflow (main or subworkflow)."""
    model_config = ConfigDict(strict=False)

    params: Optional[List[Union[str, Dict[str, Any]]]] = None
    steps: List[Step]
```

### Params Validation

Each entry in `params` is either:
- A plain `str` (required parameter)
- A single-key `Dict[str, Any]` (parameter with default value)

```python
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
                    raise ValueError(
                        "Each params dict entry must have exactly one key"
                    )
            else:
                raise ValueError(
                    f"Each params entry must be str or single-key dict, got {type(entry)}"
                )
        return v
```

---

## 4. Step (The Wrapper)

A Step is a single-key dict where key = step name, value = step body.

```python
class Step(BaseModel):
    """A named step: single-key dict {step_name: step_body}."""
    model_config = ConfigDict(strict=False)

    name: str
    body: StepBody

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError(f"Step must be a dict, got {type(data)}")
        if len(data) != 1:
            raise ValueError(
                f"Step must be a single-key dict, got {len(data)} keys: {list(data.keys())}"
            )
        name, body = next(iter(data.items()))
        return {"name": name, "body": body}
```

---

## 5. StepBody (Discriminated Union)

The step body is discriminated by key presence. We use a `model_validator(mode="before")`
on a wrapper or a custom discriminator function.

**Approach: Custom discriminator function + `Union` with `Discriminator`.**

```python
from pydantic import Discriminator, Tag
from typing import Annotated

def step_body_discriminator(data: Any) -> str:
    """Determine step type from the keys present in the dict."""
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
```

---

## 6. Individual Step Body Models

### AssignStep

```python
class AssignStep(BaseModel):
    model_config = ConfigDict(strict=False)

    assign: List[Dict[str, Any]] = Field(..., min_length=1, max_length=50)
    next: Optional[str] = Field(None, alias="next")

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
```

### CallStep

```python
class CallStep(BaseModel):
    model_config = ConfigDict(strict=False)

    call: str
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    next: Optional[str] = Field(None, alias="next")
```

### SwitchStep

```python
class SwitchStep(BaseModel):
    model_config = ConfigDict(strict=False)

    switch: List[SwitchCondition] = Field(..., min_length=1, max_length=50)
    next: Optional[str] = Field(None, alias="next")
```

### SwitchCondition

```python
class SwitchCondition(BaseModel):
    model_config = ConfigDict(strict=False)

    condition: Any  # expression string or literal true/false
    next: Optional[str] = None
    steps: Optional[List[Step]] = None
    assign: Optional[List[Dict[str, Any]]] = None
    return_: Optional[Any] = Field(None, alias="return")
    raise_: Optional[Any] = Field(None, alias="raise")
```

**Note**: `return` and `raise` are Python reserved words, so use `alias` to map from
YAML keys. The field names in the model use trailing underscores (`return_`, `raise_`).

### ReturnStep

```python
class ReturnStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    return_: Any = Field(..., alias="return")
```

### RaiseStep

```python
class RaiseStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    raise_: Any = Field(..., alias="raise")
```

### NestedStepsStep

```python
class NestedStepsStep(BaseModel):
    model_config = ConfigDict(strict=False)

    steps: List[Step]
    next: Optional[str] = Field(None, alias="next")
```

### ForStep

```python
class ForStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    for_: ForBody = Field(..., alias="for")
```

### ForBody

```python
class ForBody(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    value: str
    index: Optional[str] = None
    in_: Optional[Any] = Field(None, alias="in")
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
```

**Note**: `in` is a Python reserved word, so use `Field(alias="in")` with field name
`in_`. `for` is also reserved, so `ForStep` uses `for_` with `alias="for"`.

### ParallelStep

```python
class ParallelStep(BaseModel):
    model_config = ConfigDict(strict=False)

    parallel: ParallelBody
```

### ParallelBody

```python
class ParallelBody(BaseModel):
    model_config = ConfigDict(strict=False)

    exception_policy: Optional[Literal["continueAll"]] = None
    shared: Optional[List[str]] = None
    concurrency_limit: Optional[Union[int, str]] = None
    branches: Optional[List[Branch]] = None
    for_: Optional[ForBody] = Field(None, alias="for")

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> ParallelBody:
        has_branches = self.branches is not None
        has_for = self.for_ is not None
        if has_branches == has_for:
            raise ValueError(
                "Exactly one of 'branches' or 'for' must be specified in parallel"
            )
        if has_branches:
            if len(self.branches) < 2:
                raise ValueError("Parallel branches requires at least 2 branches")
            if len(self.branches) > 10:
                raise ValueError("Parallel branches allows at most 10 branches")
        return self
```

### Branch

```python
class Branch(BaseModel):
    """A parallel branch: single-key dict {branch_name: {steps: [...]}}."""
    model_config = ConfigDict(strict=False)

    name: str
    steps: List[Step]

    @model_validator(mode="before")
    @classmethod
    def from_raw(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError(f"Branch must be a dict, got {type(data)}")
        if len(data) != 1:
            raise ValueError("Branch must be a single-key dict")
        name, body = next(iter(data.items()))
        if not isinstance(body, dict) or "steps" not in body:
            raise ValueError(f"Branch '{name}' must have a 'steps' field")
        return {"name": name, "steps": body["steps"]}
```

### TryStep

```python
class TryStep(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    try_: TryBody = Field(..., alias="try")
    retry: Optional[RetryPolicy] = None
    except_: Optional[ExceptBody] = Field(None, alias="except")
```

### TryBody (Discriminated Union)

```python
def try_body_discriminator(data: Any) -> str:
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
```

### TryCallBody

```python
class TryCallBody(BaseModel):
    """Try body Form A: single call."""
    model_config = ConfigDict(strict=False)

    call: str
    args: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
```

### TryStepsBody

```python
class TryStepsBody(BaseModel):
    """Try body Form B: steps block."""
    model_config = ConfigDict(strict=False)

    steps: List[Step]
```

### RetryPolicy (Discriminated Union)

```python
def retry_discriminator(data: Any) -> str:
    if isinstance(data, str):
        return "predefined"
    if isinstance(data, dict):
        return "custom"
    raise ValueError("Retry must be a string expression or config dict")


RetryPolicy = Annotated[
    Union[
        Annotated[str, Tag("predefined")],
        Annotated[RetryConfig, Tag("custom")],
    ],
    Discriminator(retry_discriminator),
]
```

### RetryConfig

```python
class RetryConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    predicate: str  # expression or subworkflow reference
    max_retries: int = Field(..., gt=0)
    backoff: BackoffConfig
```

### BackoffConfig

```python
class BackoffConfig(BaseModel):
    model_config = ConfigDict(strict=False)

    initial_delay: Union[int, float]
    max_delay: Union[int, float]
    multiplier: Union[int, float]
```

### ExceptBody

```python
class ExceptBody(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)

    as_: str = Field(..., alias="as")
    steps: List[Step]
```

**Note**: `as` is a Python reserved word, so use `as_` with `alias="as"`.

---

## 7. Forward References & Rebuild

Since many models reference `Step` which references `StepBody` which references models
that contain `List[Step]` (recursive), we need forward references.

**Strategy**: Use `from __future__ import annotations` at the top of the file. Define
models in dependency order (leaf models first, then composites). At the end of the file,
call `model_rebuild()` on all models that have forward references:

```python
# At the end of models.py
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
```

---

## 8. Complete Class Dependency Graph

```
parse_workflow()
  -> SimpleWorkflow (Form A)
  -> SubworkflowsWorkflow (Form B)
       -> Dict[str, WorkflowDefinition]
            -> List[Step]
                 -> Step {name, body: StepBody}
                      -> StepBody (discriminated union)
                           -> AssignStep {assign, next?}
                           -> CallStep {call, args?, result?, next?}
                           -> SwitchStep {switch: List[SwitchCondition], next?}
                                -> SwitchCondition {condition, next?, steps?, assign?, return?, raise?}
                                     -> List[Step] (recursive)
                           -> ReturnStep {return}
                           -> RaiseStep {raise}
                           -> NestedStepsStep {steps: List[Step], next?}
                                -> List[Step] (recursive)
                           -> ForStep {for: ForBody}
                                -> ForBody {value, index?, in?|range?, steps: List[Step]}
                                     -> List[Step] (recursive)
                           -> ParallelStep {parallel: ParallelBody}
                                -> ParallelBody {exception_policy?, shared?, concurrency_limit?, branches?|for?}
                                     -> List[Branch] (recursive via steps)
                                     -> ForBody (recursive via steps)
                           -> TryStep {try: TryBody, retry?, except?}
                                -> TryBody (union)
                                     -> TryCallBody {call, args?, result?}
                                     -> TryStepsBody {steps: List[Step]}
                                -> RetryPolicy (union)
                                     -> str (predefined)
                                     -> RetryConfig {predicate, max_retries, backoff}
                                          -> BackoffConfig {initial_delay, max_delay, multiplier}
                                -> ExceptBody {as, steps: List[Step]}
```

---

## 9. Model Definition Order

Define models in this order to minimize forward reference issues:

```
1.  BackoffConfig
2.  RetryConfig
3.  ExceptBody          # forward ref to Step
4.  TryCallBody
5.  TryStepsBody        # forward ref to Step
6.  SwitchCondition     # forward ref to Step
7.  Branch              # forward ref to Step
8.  ForBody             # forward ref to Step
9.  AssignStep
10. CallStep
11. ReturnStep
12. RaiseStep
13. NestedStepsStep     # forward ref to Step
14. ForStep
15. ParallelBody        # references ForBody, Branch
16. ParallelStep
17. TryStep             # references TryBody, RetryPolicy, ExceptBody
18. step_body_discriminator function
19. StepBody type alias
20. Step                # references StepBody
21. WorkflowDefinition  # references Step
22. SimpleWorkflow       # references Step
23. SubworkflowsWorkflow # references WorkflowDefinition
24. parse_workflow()
25. model_rebuild() calls
```

---

## 10. ConfigDict Settings

All models should use:

```python
model_config = ConfigDict(strict=False, populate_by_name=True)
```

- `strict=False` -- Allow coercion from raw YAML types
- `populate_by_name=True` -- Allow access by both field name and alias

---

## 11. Validation Summary Table

| Model | Validation | Type |
|-------|-----------|------|
| `AssignStep.assign` | Min 1, max 50 entries; each is single-key dict | `field_validator` + `Field` |
| `SwitchStep.switch` | Min 1, max 50 conditions | `Field(min_length=1, max_length=50)` |
| `ForBody` | `in` XOR `range`; `index` only with `in` | `model_validator(mode="after")` |
| `ParallelBody` | `branches` XOR `for`; 2-10 branches | `model_validator(mode="after")` |
| `ParallelBody.exception_policy` | Only `"continueAll"` | `Literal["continueAll"]` |
| `RetryConfig.max_retries` | Positive integer | `Field(gt=0)` |
| `WorkflowDefinition.params` | Each entry str or single-key dict | `field_validator` |
| `Step` | Single-key dict | `model_validator(mode="before")` |
| `Branch` | Single-key dict with `steps` | `model_validator(mode="before")` |

---

## 12. Reserved Word Field Aliases

| YAML key | Python field name | Alias |
|----------|------------------|-------|
| `for` | `for_` | `"for"` |
| `in` | `in_` | `"in"` |
| `return` | `return_` | `"return"` |
| `raise` | `raise_` | `"raise"` |
| `as` | `as_` | `"as"` |
| `except` | `except_` | `"except"` |
| `try` | `try_` | `"try"` |

All of these need `Field(..., alias="keyword")` and `populate_by_name=True` in ConfigDict.

---

## 13. Parser Module

Create `src/cloud_workflows/parser.py`:

```python
import yaml
from .models import parse_workflow, Workflow

def validate_yaml(yaml_str: str) -> Workflow:
    """Parse and validate a Cloud Workflows YAML string."""
    return parse_workflow(yaml_str)

def validate_file(path: str) -> Workflow:
    """Parse and validate a Cloud Workflows YAML file."""
    with open(path, "r") as f:
        return parse_workflow(f.read())
```

---

## 14. Error Messages

When validation fails, Pydantic v2 produces structured `ValidationError` with location
info. The models should add context where helpful:

- Step parsing: Include step name in error context
- Branch parsing: Include branch name in error context
- Discriminator failures: Clear message about which keys are expected

No custom exception classes needed -- use Pydantic's built-in `ValidationError`.
