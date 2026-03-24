# Architecture

How `cloud-workflows-generator` builds, validates, and serializes Google Cloud Workflows definitions.

## Four-Layer Separation of Concerns

The codebase is organized into four distinct layers, each with a single responsibility. No layer reaches into another's domain.

```
Layer 1 — Core (dict utilities)          steps.py (private helpers)
Layer 2 — Business (step types)          steps.py, builder.py, retry.py
Layer 3 — Validation (Pydantic)          models.py, parser.py, variables.py
Layer 4 — Output (YAML)                  builder.py (build function)
```

### Layer 1: Core — Dict Utilities

Pure dict manipulation. No validation, no Pydantic, no business rules.

| Helper | Purpose |
|---|---|
| `_strip_none(d)` | Remove `None`-valued keys from a dict |
| `_expand_dotpath(key, value)` | `"a.b.c"` + `1` → `{"a": {"b": {"c": 1}}}` via jsonpath-ng |
| `_deep_merge(target, source)` | Recursively merge two nested dicts |
| `_merge_assign_items(raw_items)` | Group assign entries by root key, deep-merge shared roots, preserve bracket notation |

These are private functions inside `steps.py`. They operate on raw Python dicts and have zero knowledge of step types or workflows.

### Layer 2: Business — Step Types and Builder

Step-type classes (`Assign`, `Call`, `Switch`, `For`, etc.) and the `Steps` container. Each class gives structure and helper methods, but ultimately delegates to Layer 1 to produce `List[Dict[str, Any]]`.

**No Pydantic imports.** `build()` methods produce raw dicts directly.

```
StepType.build(step_id) → {step_id: body_dict}    (raw dict)
Steps.build()           → List[Dict]               (raw list of step dicts)
_finalize(workflow_dict) → list | dict              (raw workflow data)
```

Step classes:

```
StepType (abstract base)
  |
  +-- Assign       items: list[dict], next
  +-- Call         func, args, result, next
  +-- Return       value
  +-- Raise        value
  +-- Switch       conditions: list[Condition], next
  +-- For          value, in/range, index, steps
  +-- Parallel     branches: dict[str, Steps], shared, ...
  +-- Try          steps, retry (Retry class), error_steps
  +-- NestedSteps  steps, next
```

Retry and Backoff (`retry.py`) are also Layer 2 — they have `_to_dict()` methods that return raw dicts.

### Layer 3: Validation — Pydantic Models

A **single top-level entry point** `validate_workflow(raw_data)` takes the complete workflow output (raw dict/list from Layer 2) and validates the entire structure against the GCP Workflows spec.

The 18 internal Pydantic models (`SimpleWorkflow`, `SubworkflowsWorkflow`, `Step`, `AssignStep`, `CallStep`, etc.) exist as **implementation details** inside this layer. They enforce:

- Type constraints (field types, required/optional)
- Field constraints (max 50 assigns, 2-10 parallel branches, etc.)
- Mutual exclusivity (`items` vs `range`, `branches` vs `loop`)
- Discriminated union dispatch (step body type detection)

Also includes:

- `parse_workflow(yaml_str)` — parse a YAML string into a validated model
- `analyze_workflow(data)` — full 3-stage validation pipeline (accepts raw dicts or models)
- `to_yaml(workflow)` — serialize a validated model to YAML

The expression parser (`expressions.py`) and variable analyzer (`variables.py`) are also Layer 3.

### Layer 4: Output — YAML Serialization

`yaml.dump()` on the raw dicts from Layer 2. No Pydantic serialization involved.

```python
data = _finalize({"main": steps})   # Layer 2: raw list or dict
yaml_str = yaml.dump(data)          # Layer 4: YAML output
```

The `build()` function writes YAML files to disk using this path directly.

## Builder Pipeline

```
User code (Steps container + step classes)
    |
    v
StepType.build(step_id)                   <-- Raw dict construction
    |                                         (Layer 1 helpers used here)
    |  e.g. Assign.build("init") -> {"init": {"assign": [{"x": 10}]}}
    |       Call.build("fetch")  -> {"fetch": {"call": "http.get", ...}}
    v
Steps.build()                              <-- Collects all step dicts
    |                                         Returns List[Dict]
    v
_finalize({"main": steps, ...})            <-- Returns list (simple) or
    |                                         dict (subworkflows)
    v
build({"out.yaml": {"main": s}})          <-- yaml.dump() -> file
```

There is no Pydantic in this pipeline. The builder produces raw Python dicts which are dumped directly to YAML.

## Step Construction

Each step class stores its configuration in private attributes during `__init__()`. The `build(step_id)` method:

1. Constructs a raw dict body using Layer 1 helpers (`_strip_none`, etc.)
2. Applies reserved-word key mappings (e.g. `returns` → `"return"`, `items` → `"in"`)
3. Returns `{step_id: body_dict}`

### Reserved-Word Key Mappings

| Python param | YAML key | Used in |
|---|---|---|
| `returns` | `"return"` | `Return.build()`, `Condition._to_dict()` |
| `raises` | `"raise"` | `Raise.build()`, `Condition._to_dict()` |
| `items` | `"in"` | `For.build()` |
| (loop body) | `"for"` | `For.build()` |
| `error_steps` | `"except"` | `Try.build()` |
| (error var) | `"as"` | `Try.build()` |
| (try body) | `"try"` | `Try.build()` |

### Dot-Path Expansion

`Assign` supports dotted keys (e.g. `{"a.b.c": 1}`) via `jsonpath-ng`. The `_expand_dotpath()` helper converts `"a.b.c"` to `{"a": {"b": {"c": 1}}}` using `jsonpath_ng.parse(path).update_or_create()`.

Entries sharing the same root key are deep-merged:

```python
Assign({"config.http.timeout": 30, "config.http.retries": 3})
# → [{"config": {"http": {"timeout": 30, "retries": 3}}}]
```

Bracket-notation keys (e.g. `my_map["key"]`, `items[0]`) are preserved as-is and never merged.

### Try Body Auto-Detection

`Try._build_try_body()` inspects the serialized step dicts:
- If there is exactly one step and it contains a `"call"` key, it produces a flat call body (call fields directly in the try block).
- Otherwise it produces a nested steps body (`"steps": [...]`).

This matches GCP Workflows' two forms for try bodies.

### Retry and Backoff

Retry configuration uses dedicated builder classes (`Retry` and `Backoff` in `retry.py`):

```python
Retry(
    expr("e.code == 429"),          # predicate (positional)
    max_retries=3,                  # keyword
    backoff=Backoff(                # optional keyword
        initial_delay=1,
        max_delay=60,
        multiplier=2,
    ),
)
```

Each class has a `_to_dict()` method that converts to a raw dict at build time.

### `_UNSET` Sentinel

The `_UNSET` sentinel is used in `Condition` for `returns` and `raises` parameters, where `None` is a valid value that means "return/raise None". Absence from the constructor is represented by `_UNSET` to distinguish "not provided" from "provided as None".

## Steps Container

`Steps` is the universal step container with `.step()` for adding steps and `.merge()` for composing containers:

```python
s = Steps(params=["arg1", {"arg2": "default"}])
s.step("step_id", StepType)    # add a named step (returns self)
s.merge(other_steps)            # merge steps from another container (returns self)
```

Both `.step()` and `.merge()` return `self`, enabling method chaining:

```python
s.step("init", Assign(x=10)).step("done", Return(expr("x")))
```

Internally, `Steps` stores a list of `(step_id, StepType)` tuples. The `build()` method iterates and calls each step's `build(step_id)`.

### Finalization

`_finalize()` converts a `dict[str, Steps]` to raw workflow data:

- Single `"main"` without params → `list` (flat list of step dicts)
- Multiple workflows or `"main"` with params → `dict` of workflow definitions

Each workflow definition is `{"params": [...], "steps": [...]}` (params omitted if absent).

## Nested Step Resolution

Compound steps (For, Parallel, Try, Switch, NestedSteps) contain child step sequences. The `_resolve_steps()` helper handles conversion:

```
Input: Steps container, callable, or raw list
                |
                v
        If Steps -> .build() -> List[Dict]
                |
                v
        If callable -> create Steps, invoke, .build() -> List[Dict]
                |
                v
        If list  -> returned as-is
                |
                v
        Output: List[Dict[str, Any]]
```

Callables receive a fresh `Steps` instance, are invoked (return value ignored), and the resulting steps are serialized. This enables inline step definitions:

```python
For(
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.step("log", Call("sys.log", args={"text": expr("item")})),
)
```

## Validation Pipeline

Separate from the builder, the analysis pipeline validates a workflow against the full GCP Workflows spec. It accepts **either** raw dicts/lists (from the builder) **or** Pydantic model objects.

```
analyze_yaml(yaml_str) / analyze_workflow(data)
    |
    +- Stage 1: Structural (Pydantic v2 models)
    |    types, field constraints, mutual exclusivity
    |    Raw data is validated through Pydantic here
    |
    +- Stage 2: Expression syntax (Pratt parser)
    |    tokenize + parse every ${...} string
    |
    +- Stage 3: Variable resolution (scope analysis)
         track definitions and references across steps
```

The builder pipeline and validation pipeline are **independent**. The builder produces raw dicts with no Pydantic involvement. Validation is opt-in via `analyze_workflow()` or `validate_workflow()`.

```python
# Builder only (no validation):
data = _finalize({"main": s})
yaml_str = yaml.dump(data)

# With validation:
from cloud_workflows import analyze_workflow, validate_workflow
result = analyze_workflow(data)     # full 3-stage pipeline
model = validate_workflow(data)     # structural validation only (Layer 3)
```

## Module Map

```
src/cloud_workflows/
    __init__.py       Public API re-exports (72 symbols)
    steps.py          Layer 1+2: dict utilities + step classes (Assign, Call, etc.)
    builder.py        Layer 2+4: Steps container, _finalize(), build() → YAML files
    retry.py          Layer 2: Retry + Backoff builder classes
    models.py         Layer 3: Pydantic v2 models, validate_workflow(), parse_workflow()
    parser.py         Layer 3: analyze_yaml(), analyze_workflow()
    expressions.py    Layer 3: Pratt parser for ${...} expressions
    variables.py      Layer 3: Scope-based variable analysis
    consts.py         Constants: STDLIB_FUNCTIONS, RETRY_PREDICATES, etc.
```

For the full API reference, see [REFERENCE.md](./REFERENCE.md).
