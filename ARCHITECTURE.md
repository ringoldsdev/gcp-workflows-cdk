# Architecture

How `cloud-workflows-generator` builds, validates, and serializes Google Cloud Workflows definitions.

## Builder Pipeline

The builder constructs Pydantic model instances **eagerly** — validation happens at construction time, not as a separate post-processing step. The final YAML output is a one-way serialization of an already-validated model tree.

```
User code (StepBuilder / Workflow / Subworkflow)
    │
    ▼
Sub-builder .build()                      ← Pydantic models constructed here
    │                                        (validation runs immediately)
    │  e.g. Assign.build() → AssignStep
    │       Call.build()   → CallStep
    │       For.build()    → ForStep
    ▼
StepBuilder._append(name, body)           ← Wraps into Step(name, body)
    │
    ▼
StepBuilder.build()                       ← Returns List[Step]
    │                                        (fully validated Pydantic models)
    ▼
Workflow.build()                          ← Returns SimpleWorkflow or
    │                                        SubworkflowsWorkflow
    ▼
build([("out.yaml", workflow)])           ← Serializes to YAML files
    │
    ├─► workflow.to_dict()
    │     └─► model_dump(by_alias=True, exclude_none=True)
    │           └─► Step._serialize() / Branch._serialize()
    │                 (custom @model_serializer for single-key dict format)
    └─► yaml.dump() → file
```

There is **no re-parsing** of the final dict/YAML through Pydantic. The dict is the terminal output.

## StepBase: Dict-State Sub-Builders

All step sub-builders extend `StepBase`, which stores internal state in a plain `dict` rather than typed private fields.

```
StepBase
  │
  ├── _state: dict          Internal state store
  ├── set(path, value)      Set via jsonpath-ng (creates nested structure)
  ├── get(key, default)     Read top-level key
  ├── has(key)              Check key presence
  ├── apply(source)         Deep-merge another builder's state via deepmerge
  └── build()               Construct the Pydantic model (subclasses override)
```

### Why dict-based state

Previous versions used typed private fields (`self._func`, `self._args`, etc.) with an `_UNSET` sentinel to distinguish "not set" from `None`. This worked but required every `apply()` to hand-write field-by-field merge logic.

With `_state: dict`:
- Fields that haven't been set simply don't exist in the dict.
- `apply()` uses `deepmerge` to recursively merge two state dicts — dict keys merge, lists append, scalars override.
- `set(path, value)` uses `jsonpath-ng` to create nested structures from dot-paths (e.g. `set("a.b.c", 1)` produces `{"a": {"b": {"c": 1}}}`).

### Dependencies

| Library | Purpose | Configuration |
|---|---|---|
| `deepmerge` | `apply()` state merging | `Merger([(dict, ["merge"]), (list, ["append"])], ["override"], ["override"])` — dicts merge recursively, lists append additively, scalars override |
| `jsonpath-ng` | `set()` nested path creation | `parse(path).update_or_create(data, value)` — builds nested dict structure from dot-separated paths |

### Merge semantics by step type

| Step type | `apply()` behavior |
|---|---|
| `Assign` | `items` list appends, `next` overwrites |
| `Call` | Field-level override (custom `apply()` — args replaced wholesale, not recursively merged) |
| `Return_` / `Returns` / `DoReturn` | Value overwrites |
| `Raise_` / `Raises` / `DoRaise` | Value overwrites |
| `Switch` | `conditions` list appends, `next` overwrites |
| `For` / `Loop` | All fields overwrite, `steps` replaced |
| `Parallel` | `branches` list appends, options overwrite |
| `Try_` / `DoTry` | All fields overwrite |
| `Steps` | `body` replaced, `next` overwrites |

`Call` overrides `apply()` because its `args` dict should be replaced as a unit, not recursively merged with the target's args. All other types use the default `StepBase.apply()` deep-merge.

### `_UNSET` sentinel

The `_UNSET` sentinel is still used in one place: `Switch.condition()` defaults for `returns` and `raises` (and their deprecated aliases `return_` and `raise_`). These parameters need to distinguish "not provided" from `None` because `None` could be a valid return/raise value. Everywhere else, absence from the `_state` dict serves this purpose.

## Sub-builder class hierarchy

```
StepBase
  ├── Assign       → AssignStep         items: List[dict], next
  ├── Call         → CallStep           func, args, result, next
  ├── Return_      → ReturnStep         value       (aliases: Returns, DoReturn)
  ├── Raise_       → RaiseStep          value       (aliases: Raises, DoRaise)
  ├── Switch       → SwitchStep         conditions: List[dict], next
  ├── For          → ForStep            value, in/range, index, steps  (alias: Loop)
  ├── Parallel     → ParallelStep       branches: List[tuple], shared, ...
  ├── Try_         → TryStep            body, retry, except_as, except_steps  (alias: DoTry)
  └── Steps        → NestedStepsStep    body, next
```

Class aliases (`Returns`, `DoReturn`, `Raises`, `DoRaise`, `Loop`, `DoTry`) are simple assignments (`Returns = Return_`) — they reference the same class object, so `isinstance` checks and `apply()` type matching work transparently.

Each `.build()` method constructs its corresponding Pydantic model. Pydantic validates field types, constraints (e.g. 1-50 assigns, mutual exclusivity of `in`/`range`), and alias mappings at that moment.

## Nested step resolution

Compound steps (For, Parallel, Try, Switch, Steps) can contain child step sequences. These children are typically provided as a `StepBuilder` or a lambda that configures one.

`_resolve_step_builder()` handles the conversion:

```
Input: StepBuilder, lambda, or raw list
                │
                ▼
        If callable → create StepBuilder, invoke callback
                │
                ▼
        If StepBuilder → .build() → List[Step]
                │
                ▼
        Serialize each: {step.name: step.body.model_dump(...)}
                │
                ▼
        Output: List[Dict[str, Any]]
```

The resulting list of dicts is passed to the parent Pydantic model constructor (e.g. `ForBody(steps=step_dicts)`), where Pydantic re-validates each dict through the `Step` model validator. This means nested steps go through a **serialize → re-validate** round-trip, which ensures structural integrity at every nesting level.

## Validation pipeline

Separate from the builder, the analysis pipeline validates a workflow against the full GCP Workflows spec:

```
analyze_yaml(yaml_str) / analyze_workflow(workflow)
    │
    ├─ Stage 1: Structural (Pydantic v2 models)
    │    types, field constraints, mutual exclusivity
    │
    ├─ Stage 2: Expression syntax (Pratt parser)
    │    tokenize + parse every ${...} string
    │
    └─ Stage 3: Variable resolution (scope analysis)
         track definitions and references across steps
```

The builder pipeline and analysis pipeline are independent. Builder construction runs Pydantic validation (Stage 1) eagerly. `analyze_workflow()` adds Stages 2 and 3 on top when explicitly called.

## Module map

```
src/cloud_workflows/
    __init__.py       Public API re-exports
    models.py         Pydantic v2 models, serializers, discriminated unions
    builder.py        StepBuilder, Workflow, Subworkflow, WorkflowBuilder, build()
    steps.py          StepBase + 9 sub-builder classes
    expressions.py    Pratt parser for ${...} expressions
    variables.py      Scope-based variable analysis
    parser.py         analyze_yaml(), analyze_workflow()
```

For the full API reference, see [REFERENCE.md](./REFERENCE.md).
