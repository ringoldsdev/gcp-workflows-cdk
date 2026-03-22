# Architecture

How `cloud-workflows-generator` builds, validates, and serializes Google Cloud Workflows definitions.

## Builder Pipeline

The builder constructs Pydantic model instances **eagerly** -- validation happens at construction time, not as a separate post-processing step. The final YAML output is a one-way serialization of an already-validated model tree.

```
User code (Steps container + step classes)
    |
    v
StepType.build(step_id)                   <-- Pydantic models constructed here
    |                                         (validation runs immediately)
    |  e.g. Assign.build("init") -> AssignStep
    |       Call.build("fetch")  -> CallStep
    |       For.build("loop")   -> ForStep
    v
model_dump(by_alias=True, exclude_none=True)
    |                                         Returns {step_id: body_dict}
    v
Steps.build()                              <-- Collects all step dicts
    |                                         Returns List[Dict]
    v
_finalize() / build({...})                 <-- Returns SimpleWorkflow or
    |                                         SubworkflowsWorkflow
    v
build({"out.yaml": workflow})              <-- Serializes to YAML files
    |                                         (auto-finalizes Steps objects)
    |
    +-> workflow.to_dict()
    |     +-> model_dump(by_alias=True, exclude_none=True)
    |           +-> Step._serialize() / Branch._serialize()
    |                 (custom @model_serializer for single-key dict format)
    +-> yaml.dump() -> file
```

There is **no re-parsing** of the final dict/YAML through Pydantic. The dict is the terminal output.

## Step Classes

All step types extend `StepType`, a base class with a single `build(step_id) -> dict` method. Each step class is an immutable description of a step's configuration.

```
StepType
  |
  +-- Assign      -> AssignStep         items: list[dict], next
  +-- Call        -> CallStep           func, args, result, next
  +-- Return      -> ReturnStep         value
  +-- Raise       -> RaiseStep          value
  +-- Switch      -> SwitchStep         conditions: list[Condition], next
  +-- For         -> ForStep            value, in/range, index, steps
  +-- Parallel    -> ParallelStep       branches: dict[str, Steps], shared, ...
  +-- Try         -> TryStep            steps, retry, except_
  +-- NestedSteps -> NestedStepsStep    steps, next
```

### Construction pattern

Each step class stores its configuration in private attributes during `__init__()`. No Pydantic model is constructed at init time. The `build(step_id)` method:

1. Constructs the corresponding Pydantic model (which triggers validation).
2. Calls `model_dump(by_alias=True, exclude_none=True)` on the model.
3. Returns `{step_id: body_dict}`.

This means validation errors surface at `build()` time, not at step construction time. Since `Steps.build()` calls every step's `build()`, all validation runs when the container is serialized.

### Dot-path expansion

`Assign` supports dotted keys (e.g. `{"a.b.c": 1}`) via `jsonpath-ng`. The `_expand_dotpath()` helper converts `"a.b.c"` to `{"a": {"b": {"c": 1}}}` using `jsonpath_ng.parse(path).update_or_create()`.

### Try body auto-detection

`Try._build_try_body()` inspects the serialized step dicts:
- If there is exactly one step and it contains a `"call"` key, it produces a `TryCallBody` (flat call fields in the try block).
- Otherwise it produces a `TryStepsBody` (nested steps list).

This matches GCP Workflows' two forms for try bodies.

### `_UNSET` sentinel

The `_UNSET` sentinel is used in `Condition` for `return_` and `raise_` parameters, where `None` is a valid value that means "return/raise None". Absence from the constructor is represented by `_UNSET` to distinguish "not provided" from "provided as None".

## Steps Container

`Steps` is the universal step container with an overloaded `__call__` protocol:

```python
s = Steps(params=["arg1", {"arg2": "default"}])
s("step_id", StepType)    # add a named step
s(other_steps)             # merge steps from another container
```

Internally, `Steps` stores a list of `(step_id, StepType)` tuples. The `build()` method iterates and calls each step's `build(step_id)`.

### Finalization

`_finalize()` converts a `Steps` container to a Pydantic workflow model:
- No params -> `SimpleWorkflow`
- With params -> `SubworkflowsWorkflow` (single "main" workflow)

The `build()` function handles multi-workflow finalization:
- `dict[str, Steps]` -> `SubworkflowsWorkflow`
- Single `"main"` without params collapses to `SimpleWorkflow`

## Nested Step Resolution

Compound steps (For, Parallel, Try, Switch, NestedSteps) contain child step sequences. The `_resolve_steps()` helper handles conversion:

```
Input: Steps container or raw list
                |
                v
        If Steps -> .build() -> List[Dict]
                |
                v
        If list  -> returned as-is
                |
                v
        Output: List[Dict[str, Any]]
```

The resulting list of dicts is passed to the parent Pydantic model constructor (e.g. `ForBody(steps=step_dicts)`), where Pydantic re-validates each dict through the `Step` model validator. This means nested steps go through a **serialize -> re-validate** round-trip, which ensures structural integrity at every nesting level.

## Validation Pipeline

Separate from the builder, the analysis pipeline validates a workflow against the full GCP Workflows spec:

```
analyze_yaml(yaml_str) / analyze_workflow(workflow)
    |
    +- Stage 1: Structural (Pydantic v2 models)
    |    types, field constraints, mutual exclusivity
    |
    +- Stage 2: Expression syntax (Pratt parser)
    |    tokenize + parse every ${...} string
    |
    +- Stage 3: Variable resolution (scope analysis)
         track definitions and references across steps
```

The builder pipeline and analysis pipeline are independent. Builder construction runs Pydantic validation (Stage 1) eagerly. `analyze_workflow()` adds Stages 2 and 3 on top when explicitly called.

## Module Map

```
src/cloud_workflows/
    __init__.py       Public API re-exports
    models.py         Pydantic v2 models, serializers, discriminated unions
    builder.py        Steps container + build() function
    steps.py          StepType base + step classes (Assign, Call, Switch, etc.)
    expressions.py    Pratt parser for ${...} expressions
    variables.py      Scope-based variable analysis
    parser.py         analyze_yaml(), analyze_workflow()
```

For the full API reference, see [REFERENCE.md](./REFERENCE.md).
