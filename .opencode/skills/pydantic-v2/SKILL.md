---
name: pydantic-v2
description: Pydantic v2 patterns used in the cloud_workflows codebase — model config, aliases, discriminated unions, validators, serializers, forward references, and known gotchas
---

# Pydantic v2 Patterns — cloud_workflows

Reference docs: https://docs.pydantic.dev/latest/llms.txt

## Patterns in use

### 1. BaseModel + ConfigDict

Every model uses:

```python
class MyModel(BaseModel):
    model_config = ConfigDict(strict=False, populate_by_name=True)
```

- `strict=False` — allows coercion (e.g., int to float in BackoffConfig).
- `populate_by_name=True` — required so that programmatic construction can use the Python field name (`return_`) while YAML parsing uses the alias (`return`).

All 18 model classes repeat this config. A shared base class was considered but rejected: the explicit repetition is low-cost (one line), avoids inheritance complexity, and keeps each model self-contained.

### 2. Field aliases for Python reserved words

Seven fields alias Python reserved words:

| Python name | Alias | Model(s) |
|---|---|---|
| `return_` | `"return"` | ReturnStep, SwitchCondition |
| `raise_` | `"raise"` | RaiseStep, SwitchCondition |
| `for_` | `"for"` | ForStep, ParallelBody |
| `in_` | `"in"` | ForBody |
| `as_` | `"as"` | ExceptBody |
| `except_` | `"except"` | TryStep |
| `try_` | `"try"` | TryStep |

Pattern: `field_: Type = Field(..., alias="keyword")`

Combined with `populate_by_name=True`, these work in both directions:
- YAML parsing: Pydantic reads the alias key from the dict.
- Programmatic: `ReturnStep(return_="value")` uses the field name.
- Serialization: `model_dump(by_alias=True)` emits the alias.

### 3. Field constraints

- `Field(..., gt=0)` — `RetryConfig.max_retries` (positive integer).
- `Field(..., min_length=1, max_length=50)` — `AssignStep.assign`, `SwitchStep.switch` (list bounds).

### 4. Discriminated unions with callable Discriminator

Three discriminated unions use `Annotated[Union[...], Discriminator(func)]` + `Tag(...)`:

- **StepBody** (9 variants) — `step_body_discriminator`
- **TryBody** (2 variants) — `try_body_discriminator`
- **RetryPolicy** (2 variants) — `retry_discriminator`

Each discriminator function handles **both** raw dict input (YAML parsing) and model instance input (programmatic construction). This dual handling is required per the Pydantic docs: "When you're designing callable discriminators, remember that you might have to account for both dict and model type inputs."

Example pattern:

```python
def step_body_discriminator(data: Any) -> str:
    # Handle model instances
    if isinstance(data, AssignStep):
        return "assign"
    # Handle raw dicts
    if isinstance(data, dict):
        if "assign" in data:
            return "assign"
    raise ValueError(...)

StepBody = Annotated[
    Union[
        Annotated[AssignStep, Tag("assign")],
        ...
    ],
    Discriminator(step_body_discriminator),
]
```

### 5. model_validator(mode="before") for structural reshaping

Four models use `@model_validator(mode="before")` to transform input structure:

- **Step** — `{step_name: step_body}` single-key dict → `{"name": ..., "body": ...}`
- **Branch** — `{branch_name: {"steps": [...]}}` → `{"name": ..., "steps": [...]}`
- **SimpleWorkflow** — `[steps_list]` → `{"steps": [...]}`
- **SubworkflowsWorkflow** — `{"main": {...}, "helper": {...}}` → `{"workflows": {...}}`

All four include an early-return for programmatic construction:

```python
@model_validator(mode="before")
@classmethod
def from_raw(cls, data: Any) -> Any:
    if "name" in data and "body" in data:
        return data  # programmatic construction
    # ... reshape YAML input
```

### 6. model_validator(mode="after") for cross-field validation

Two models use `@model_validator(mode="after")` for mutual exclusivity checks:

- **ForBody** — exactly one of `in_` or `range`; `index` only with `in_`.
- **ParallelBody** — exactly one of `branches` or `for_`; branches count 2-10.

### 7. field_validator(mode="before")

Two uses:

- **AssignStep.assign** — validates each entry is a single-key dict.
- **WorkflowDefinition.params** — validates each entry is str or single-key dict.

### 8. @model_serializer (plain mode) for reversing structural transforms

Step and Branch use `@model_serializer` (plain mode, NOT wrap mode) to reverse their `model_validator` reshaping:

```python
@model_serializer
def _serialize(self) -> Dict[str, Any]:
    body_dict = self.body.model_dump(by_alias=True, exclude_none=True)
    return {self.name: body_dict}
```

**Why plain mode, not wrap mode**: `@model_serializer(mode='wrap')` was attempted but the `handler(self)` output was unreliable when called from a parent model's `model_dump()` — the handler produced different output in nested vs direct invocations. Plain mode gives full control by calling `model_dump()` on child fields directly.

### 9. model_dump() conventions

Standard call pattern throughout:

```python
model_dump(by_alias=True, exclude_none=True)
```

- `by_alias=True` — emits YAML-compatible keys (`return` not `return_`).
- `exclude_none=True` — omits optional fields that are None.

### 10. model_validate() for parsing

`parse_workflow()` in parser.py uses `SimpleWorkflow.model_validate(raw)` or `SubworkflowsWorkflow.model_validate(raw)` after `yaml.safe_load()`.

### 11. model_rebuild() for forward references

10 calls at module end resolve forward references caused by `from __future__ import annotations`:

```python
Step.model_rebuild()
SwitchCondition.model_rebuild()
ForBody.model_rebuild()
# ... etc
```

Required because `List[Step]` appears in models defined before `Step`.

### 12. Forward references with `from __future__ import annotations`

The module uses `from __future__ import annotations` to allow forward type references. Models are defined leaf-first (BackoffConfig, RetryConfig, etc.) with forward refs to Step resolved at module end via `model_rebuild()`.

## Considered but not applied

### serialize_by_alias in ConfigDict

`ConfigDict(serialize_by_alias=True)` would eliminate the need to pass `by_alias=True` to every `model_dump()` call. Not applied because:
- Only Step and Branch serializers call `model_dump()` internally.
- `to_dict()` on workflow types also call it, but there are only 2 such methods.
- The explicit `by_alias=True` at call sites is clearer about intent.

### Separate validation_alias / serialization_alias

Could split `alias="return"` into `validation_alias="return"` + `serialization_alias="return"`. Not applied because both directions use the same alias, so a single `alias` is simpler.

### exclude_if on Field (Pydantic 2.11+)

New feature: `Field(exclude_if=lambda v: v is None)` per-field. Not applied because `exclude_none=True` on `model_dump()` already handles this globally and is less verbose.

### Shared base class

Extracting `model_config = ConfigDict(...)` into a `BaseWorkflowModel` base class. Not applied because the config is one line per class and a base class adds an inheritance layer with no real benefit for 18 simple models.

### Annotated validators

Using `Annotated[Type, BeforeValidator(func)]` instead of `@field_validator` decorators. Not applied because the decorator style is used consistently and the validators are class-specific (not reusable across fields).

## Key gotchas

1. **Discriminator functions must handle both dict and model inputs** — when a parent model's field uses `Discriminator(func)`, and the parent is constructed programmatically with a model instance, the discriminator receives the model instance, not a dict.

2. **model_validator(mode="before") must handle programmatic construction** — when you do `Step(name="foo", body=AssignStep(...))`, the validator receives `{"name": "foo", "body": <AssignStep>}`. It must detect this and return early, not try to reshape it as YAML input.

3. **@model_serializer wrap mode is unreliable with nesting** — the `handler(self)` output differs when called from `parent.model_dump()` vs `model.model_dump()` directly. Use plain mode instead and call `child.model_dump()` explicitly.

4. **model_rebuild() order doesn't matter** — Pydantic resolves all forward refs at rebuild time regardless of call order. But all forward-referencing models must be rebuilt before any validation or serialization occurs.

5. **populate_by_name=True is required for dual-mode (YAML + programmatic)** — without it, programmatic construction must use the alias name, which for Python keywords would require `ReturnStep(**{"return": value})` instead of `ReturnStep(return_=value)`.
