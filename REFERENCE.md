# Reference

Comprehensive technical reference for `cloud-workflows-generator`. For usage examples, see [README.md](./README.md).

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Public API](#public-api)
- [Builder API](#builder-api)
- [Pydantic Models](#pydantic-models)
- [Architecture](#architecture)
- [Expression Parser](#expression-parser)
- [Variable Analysis](#variable-analysis)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)

---

## Requirements

- Python >= 3.14
- pydantic >= 2.0
- pyyaml >= 6.0
- jsonpath-ng >= 1.6
- pytest >= 8.0 (dev only)

## Installation

```bash
pip install -e .

# with dev dependencies
pip install -e ".[dev]"
```

---

## Public API

Everything is importable from `cloud_workflows`.

### Parsing

| Function | Description |
|---|---|
| `parse_workflow(yaml_str)` | Parse a YAML string into a `Workflow` model (`SimpleWorkflow` or `SubworkflowsWorkflow`) |

### Serialization

| Function | Description |
|---|---|
| `to_yaml(workflow)` | Serialize a `Workflow` model to a YAML string |
| `expr(body)` | Wrap a string in `${...}` — `expr("x + 1")` returns `"${x + 1}"` |
| `concat(items, separator)` | Build a `+` concatenation expression from a list of items. Items can be `expr()` values, plain strings (auto-quoted), numbers, booleans, or `None`. Separator defaults to `""`. |
| `workflow.to_dict()` | Serialize to Python dict/list (method on `SimpleWorkflow`/`SubworkflowsWorkflow`) |
| `workflow.to_yaml()` | Serialize to YAML string (method on `SimpleWorkflow`/`SubworkflowsWorkflow`) |

### Analysis

| Function | Description |
|---|---|
| `analyze_yaml(yaml_str)` | Parse YAML + validate expressions + analyze variables. Returns `AnalysisResult` |
| `analyze_workflow(data)` | Same as `analyze_yaml` but takes raw data (list/dict from builder) or a Pydantic model (no YAML round-trip) |
| `validate_workflow(data)` | Structural validation only. Takes raw data, returns a validated Pydantic `Workflow` model |

`AnalysisResult` fields:

| Field | Type | Description |
|---|---|---|
| `.workflow` | `Workflow` | The parsed Pydantic model |
| `.expression_errors` | `list[ExpressionError]` | Invalid `${...}` syntax errors |
| `.variable_issues` | `list[VariableIssue]` | Variable reference issues (errors and warnings) |
| `.is_valid` | `bool` | `True` if no expression errors and no variable errors |
| `.errors` | `list` | Combined list of all errors |
| `.warnings` | `list` | Variable warnings (e.g. conditionally-defined variables) |

### Expression Validation (Standalone)

| Function | Description |
|---|---|
| `validate_expression(expr_body)` | Validate a single expression body (without `${}`). Returns `None` if valid, `ExpressionError` if not |
| `validate_all_expressions(value)` | Recursively find and validate all `${...}` in a value tree |
| `extract_expression_strings(value)` | Extract expression bodies from a value tree |
| `extract_variable_references(expr)` | Extract root variable names referenced in an expression |

### Expression AST

| Function / Type | Description |
|---|---|
| `parse_expression_ast(expr_body)` | Parse an expression into an AST. Raises `ExpressionError` on invalid syntax |
| `parse_expression_recover(expr_body)` | Parse with error recovery. Returns `(node, errors)` |
| `walk(node)` | Depth-first pre-order traversal of an AST node. Returns `list[Node]` |
| `Node` | Union of all AST node types |
| `NumberLiteral`, `StringLiteral`, `BoolLiteral`, `NullLiteral` | Literal nodes |
| `Identifier` | Variable/function name node |
| `UnaryOp`, `BinaryOp` | Operator nodes |
| `MemberAccess`, `IndexAccess`, `FunctionCall` | Postfix access nodes |
| `ListLiteral`, `MapLiteral`, `MapEntry` | Collection nodes |
| `ErrorNode` | Placeholder for invalid syntax (error recovery mode) |

### Variable Analysis (Standalone)

| Function / Type | Description |
|---|---|
| `analyze_variables(workflow)` | Analyze a `Workflow` model for variable issues. Returns `list[VariableIssue]` |
| `VariableIssue` | Dataclass: `.severity`, `.message`, `.variable`, `.step_name`, `.workflow_name` |
| `Severity` | Enum: `ERROR`, `WARNING` |

---

## Builder API

The builder API provides a class-based, imperative approach to constructing workflows.

### Steps

`Steps` is the universal container for workflow steps. The primary API uses convenience alias methods (`.assign()`, `.call()`, `.returns()`, etc.) that mirror each step type. For full control, the generic `.step()` method accepts any `StepType` instance directly.

```python
# Preferred: alias methods
s = (Steps()
    .assign("init", x=10, y=20)
    .call("log", "sys.log", args={"text": expr("x")})
    .returns("done", expr("x + y")))

# Generic: .step() with StepType instances
s = (Steps()
    .step("init", Assign(x=10, y=20))
    .step("log", Call("sys.log", args={"text": expr("x")}))
    .step("done", Return(expr("x + y"))))
```

| Method | Description |
|---|---|
| `s.step("name", step)` | Add a named step. `step` must be a `StepType` instance. Returns `self`. |
| `s.merge(other)` | Merge all steps from another `Steps` instance (appends in order). Returns `self`. |
| `s.build()` | Serialize to `list[dict]` — each entry is `{step_id: body}`. |
| `len(s)` | Number of steps. |

Constructor:

```python
Steps(*, params=None)
```

| Arg | Description |
|---|---|
| `params` | Optional `list` of parameter names (strings) or parameter dicts with defaults (e.g. `[{"timeout": 30}]`). When set, the container represents a subworkflow. |

#### Alias Methods

All alias methods take `step_id` as their first argument, then mirror the corresponding `StepType` constructor parameters. All return `self` for chaining.

| Method | Delegates to | Signature |
|---|---|---|
| `.assign(step_id, mapping?, /, *, next?, **kwargs)` | `Assign` | Variable assignments via kwargs and/or dict mapping. |
| `.call(step_id, func, *, args?, result?, next?)` | `Call` | Function/subworkflow call. |
| `.returns(step_id, value)` | `Return` | Return a value. Named `returns` to avoid Python keyword `return`. |
| `.raises(step_id, value)` | `Raise` | Raise an error. Named `raises` to avoid Python keyword `raise`. |
| `.switch(step_id, conditions, /, *, next?)` | `Switch` | Conditional branching with list of `Condition` objects. |
| `.loop(step_id, *, value, items?, range?, index?, steps)` | `For` | For-loop iteration. |
| `.parallel(step_id, *, branches, shared?, exception_policy?, concurrency_limit?)` | `Parallel` | Parallel branches. |
| `.do_try(step_id, *, steps, retry?, error_steps?)` | `Try` | Try/retry/except. Named `do_try` to avoid Python keyword `try`. |
| `.nested(step_id, *, steps, next?)` | `NestedSteps` | Nested step group. Alias for `.steps()`. |
| `.steps(step_id, *, steps, next?)` | `NestedSteps` | Nested step group. Alias for `.nested()`. |

Example with full chaining:

```python
from cloud_workflows import Steps, Condition, Retry, Backoff, expr

inner = Steps().call("log", "sys.log", args={"text": expr("item")})
body = Steps().call("fetch", "http.get",
                    args={"url": "https://example.com"},
                    result="resp")

s = (Steps()
    .assign("init", x=10, y=20)
    .call("log", "sys.log", args={"text": expr("x")})
    .switch("check", [
        Condition(expr("x > 0"), next="positive"),
        Condition(True, next="negative"),
    ])
    .loop("iterate", value="item", items=["a", "b", "c"], steps=inner)
    .do_try("safe",
            steps=body,
            retry=Retry(expr("e.code == 429"), max_retries=3,
                        backoff=Backoff(initial_delay=1, max_delay=30, multiplier=2)))
    .returns("done", expr("x + y")))
```

#### Method Chaining

All methods (`.assign()`, `.call()`, `.step()`, `.merge()`, etc.) return `self`, enabling fluent chains:

```python
s = (Steps()
    .assign("init", x=10)
    .call("log", "sys.log", args={"text": expr("x")})
    .returns("done", expr("x")))
```

### Step Classes

All step classes extend `StepType`. Each has a `build(step_id) -> dict` method that returns `{step_id: <body>}`.

#### Assign

```python
Assign(mapping=None, /, *, next=None, **kwargs)
```

| Arg | Description |
|---|---|
| `mapping` | Optional dict with dotted-path keys (e.g. `{"a.b.c": 1}`). Dot-separated keys auto-expand to nested dicts via `jsonpath-ng`. |
| `next` | Jump target step name. |
| `**kwargs` | Simple variable assignments. |

At least one assignment (from `mapping` or `kwargs`) is required.

#### Call

```python
Call(func, *, args=None, result=None, next=None)
```

| Arg | Description |
|---|---|
| `func` | Function name to call (required). |
| `args` | Dict of keyword arguments. |
| `result` | Variable name to store the return value. |
| `next` | Jump target step name. |

#### Return

```python
Return(value)
```

| Arg | Description |
|---|---|
| `value` | The value to return (required). Can be any value including `None`. |

#### Raise

```python
Raise(value)
```

| Arg | Description |
|---|---|
| `value` | The error value to raise (required). Can be a string, dict, expression, etc. |

#### Switch

```python
Switch(conditions, /, *, next=None)
```

| Arg | Description |
|---|---|
| `conditions` | Positional list of `Condition` objects (at least one required). |
| `next` | Default fallthrough target. |

#### Condition

```python
Condition(condition, *, next=None, steps=None, assign=None, returns=UNSET, raises=UNSET)
```

| Arg | Description |
|---|---|
| `condition` | The condition expression. |
| `next` | Jump target. |
| `steps` | Inline `Steps` container or callable to execute. |
| `assign` | Inline assignments (list of single-key dicts). |
| `returns` | Return value if condition is true. Uses `_UNSET` sentinel; `None` is a valid value. |
| `raises` | Raise value if condition is true. Uses `_UNSET` sentinel; `None` is a valid value. |

#### For

```python
For(*, value, items=None, range=None, index=None, steps)
```

| Arg | Description |
|---|---|
| `value` | Loop variable name (required). |
| `items` | Collection to iterate (mutually exclusive with `range`). Accepts a list, expression, or any value. |
| `range` | Range specification `[start, end]` or `[start, end, step]`. |
| `index` | Optional index variable name. |
| `steps` | Loop body — `Steps` container, callable, or list of dicts (required). |

#### Parallel

```python
Parallel(*, branches, shared=None, exception_policy=None, concurrency_limit=None)
```

| Arg | Description |
|---|---|
| `branches` | Dict of `{name: Steps}` or `{name: callable}` (at least one required). |
| `shared` | List of shared variable names. |
| `exception_policy` | Exception handling policy (e.g. `"continueAll"`). |
| `concurrency_limit` | Max concurrent branches. |

#### Try

```python
Try(*, steps, retry=None, error_steps=None)
```

| Arg | Description |
|---|---|
| `steps` | Try body — `Steps` container, callable, or list of dicts (required). |
| `retry` | Optional `Retry` instance for retry configuration. |
| `error_steps` | Except handler steps — `Steps` container, callable, or list of dicts. The error variable is always bound to `e`. |

Try body auto-detection: if the body is a single Call step, it produces a `TryCallBody` (flat call fields); otherwise a `TryStepsBody` (nested steps list).

#### Retry

```python
Retry(predicate, *, max_retries, backoff=None)
```

| Arg | Description |
|---|---|
| `predicate` | Retry predicate — a string name (e.g. `"http.default_retry"`) or an expression (positional). |
| `max_retries` | Maximum number of retry attempts (keyword). |
| `backoff` | Optional `Backoff` instance for exponential backoff (keyword). |

#### Backoff

```python
Backoff(*, initial_delay, max_delay, multiplier)
```

| Arg | Description |
|---|---|
| `initial_delay` | Initial delay in seconds before the first retry. |
| `max_delay` | Maximum delay in seconds between retries. |
| `multiplier` | Multiplier applied to the delay after each retry. |

#### NestedSteps

```python
NestedSteps(*, steps, next=None)
```

| Arg | Description |
|---|---|
| `steps` | Nested `Steps` container, callable, or list of dicts. |
| `next` | Jump target step name. |

### Callables for Inline Steps

Wherever a compound step accepts a `steps` parameter (`.loop()`, `.parallel()` branches, `.do_try()`, `.switch()` conditions, `.nested()` / `.steps()`), you can pass a callable instead of a `Steps` instance. The callable receives a fresh `Steps` and its return value is ignored:

```python
s.loop("loop",
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.call("log", "sys.log", args={"text": expr("item")}),
)
```

### _finalize() Function

```python
_finalize(workflow_dict: dict[str, Steps]) -> list | dict
```

Converts a `dict[str, Steps]` with a required `"main"` key into raw workflow data:

| Type | Behavior |
|---|---|
| `dict[str, Steps]` with only `"main"` (no params) | Returns a `list` (flat step list). |
| `dict[str, Steps]` with `"main"` + other keys | Returns a `dict` of named workflow definitions. |
| `dict[str, Steps]` with `"main"` having params | Returns a `dict` of named workflow definitions. |

### build() Function

```python
build(workflows: dict[str, dict[str, Steps]], output_dir: str | Path = ".") -> list[Path]
```

Writes each `{filename: {name: Steps}}` entry as a YAML file to `output_dir`. Creates directories as needed. Returns the list of written file paths.

Each workflow value must be a `dict[str, Steps]` with a required `"main"` key. Internally calls `_finalize()` and `yaml.dump()`:

| Type | Behavior |
|---|---|
| `dict[str, Steps]` with only `"main"` (no params) | Produces flat step list YAML. |
| `dict[str, Steps]` with `"main"` + other keys | Produces named workflows YAML. |
| `dict[str, Steps]` with `"main"` having params | Produces named workflows YAML. |

### Composition

Steps containers are composable via `.merge()`:

```python
common = Steps().call("log", "sys.log", args={"text": "starting"})

main = (Steps()
    .merge(common)
    .returns("done", "ok"))
```

Factory functions that return `Steps` instances are the primary composition pattern:

```python
def logging_steps(message):
    return Steps().call("log", "sys.log", args={"text": message})

main = (Steps()
    .assign("init", status="starting")
    .merge(logging_steps("Workflow started"))
    .returns("done", "ok"))
```

---

## Pydantic Models (Layer 3)

The Pydantic models live in Layer 3 (Validation). They are used by `validate_workflow()`, `parse_workflow()`, and `analyze_workflow()` for structural validation. The builder (Layer 2) does **not** use these models — it produces raw dicts directly.

All models use `model_dump(by_alias=True, exclude_none=True)` for serialization. `Step` and `Branch` have custom `@model_serializer` decorators to handle their single-key dict format.

### Workflow Types

| Model | Description |
|---|---|
| `SimpleWorkflow(steps: list[Step])` | Form A — flat list of steps (no subworkflows, no params) |
| `SubworkflowsWorkflow(workflows: dict[str, WorkflowDefinition])` | Form B — named workflows with optional params |
| `WorkflowDefinition(params: list, steps: list[Step])` | A single workflow definition (used in Form B) |
| `Workflow` | Type alias: `Union[SimpleWorkflow, SubworkflowsWorkflow]` |

### Step Model

`Step(name: str, body: StepBody)` — A named step. `StepBody` is a discriminated union of all step body types. Parses from / serializes to a single-key dict `{name: body_dict}`.

### Step Body Types

| Model | Discriminating key | Optional fields |
|---|---|---|
| `AssignStep(assign: list[dict])` | `assign` | `next` |
| `CallStep(call: str)` | `call` | `args`, `result`, `next` |
| `ReturnStep(returns: Any)` | `return` | — |
| `RaiseStep(raises: Any)` | `raise` | — |
| `SwitchStep(switch: list[SwitchCondition])` | `switch` | `next` (fallthrough) |
| `ForStep(loop: ForBody)` | `for` | — |
| `ParallelStep(parallel: ParallelBody)` | `parallel` | — |
| `TryStep(steps: TryBody)` | `try` | `retry`, `error_steps` |
| `NestedStepsStep(steps: list[Step])` | `steps` | `next` |

### Supporting Models

| Model | Fields |
|---|---|
| `SwitchCondition` | `condition`, `next?`, `steps?`, `assign?`, `returns?`, `raises?` |
| `ForBody` | `value`, `items?` (mutually exclusive with `range`), `range?`, `index?`, `steps` |
| `ParallelBody` | `branches?` (mutually exclusive with `loop`), `loop?`, `shared?`, `exception_policy?`, `concurrency_limit?` |
| `Branch(name, steps)` | Single-key dict serialization |
| `TryCallBody(call, args?, result?)` | Try body form A |
| `TryStepsBody(steps)` | Try body form B |
| `ExceptBody(alias, steps)` | Except handler |
| `RetryConfig(predicate, max_retries, backoff?)` | Custom retry configuration |
| `BackoffConfig(initial_delay, max_delay, multiplier)` | Exponential backoff settings |

### Validation Constraints

- `AssignStep.assign`: 1-50 entries, each must be a single-key dict
- `SwitchStep.switch`: 1-50 conditions
- `ParallelBody.branches`: 2-10 branches
- `ForBody`: exactly one of `items` or `range` must be set
- `ParallelBody`: exactly one of `branches` or `loop` must be set

### Field Aliases

Python reserved words use descriptive suffixes as field names. Pydantic aliases handle YAML serialization:

| Field | Alias |
|---|---|
| `returns` | `return` |
| `raises` | `raise` |
| `loop` | `for` |
| `items` | `in` |
| `alias` | `as` |
| `error_steps` | `except` |
| `steps` | `try` |

---

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full 4-layer separation of concerns, builder pipeline, and validation pipeline diagrams.

### Layer Overview

| Layer | Responsibility | Modules | Pydantic? |
|---|---|---|---|
| **1. Core** | Dict utilities (`_strip_none`, `_expand_dotpath`, `_deep_merge`) | `steps.py` (private) | No |
| **2. Business** | Step classes, `Steps` container, `_finalize()` | `steps.py`, `builder.py`, `retry.py` | No |
| **3. Validation** | Structural validation, expression parsing, variable analysis | `models.py`, `parser.py`, `expressions.py`, `variables.py` | Yes |
| **4. Output** | `yaml.dump()` on raw dicts | `builder.py` (`build()`) | No |

### Module Map

```
src/cloud_workflows/
    __init__.py       Public API re-exports (72 symbols)
    steps.py          Layer 1+2: dict utilities + step classes (Assign, Call, etc.)
    builder.py        Layer 2+4: Steps container, _finalize(), build() → YAML files
    retry.py          Layer 2: Retry + Backoff builder classes
    models.py         Layer 3: Pydantic v2 models, validate_workflow(), parse_workflow()
    parser.py         Layer 3: analyze_yaml(), analyze_workflow()
    expressions.py    Layer 3: Pratt parser for ${...} expressions
    variables.py      Layer 3: Scope-based variable tracking
    consts.py         Constants: STDLIB_FUNCTIONS, RETRY_PREDICATES, etc.
```

### Processing Pipeline

`analyze_yaml(yaml_str)` and `analyze_workflow(data)` run three stages. `analyze_workflow()` accepts raw dicts/lists (from the builder) or Pydantic model objects.

```
                   YAML string / raw data / Workflow model
                               |
                               v
            +-----------------------------------+
            |  Stage 1: Structural Validation   |
            |  (models.py -- Pydantic v2)       |
            |                                   |
            |  Raw data validated through       |
            |  Pydantic: types, field           |
            |  constraints, mutual exclusivity  |
            |  Output: Workflow model tree       |
            +-----------------------------------+
                              |
                              v
            +-----------------------------------+
            |  Stage 2: Expression Validation   |
            |  (expressions.py)                 |
            |                                   |
            |  Walks raw YAML value tree, finds |
            |  all ${...} strings, tokenizes    |
            |  and parses each with Pratt       |
            |  parser to check syntax           |
            |  Output: list[ExpressionError]    |
            +-----------------------------------+
                              |
                              v
            +-----------------------------------+
            |  Stage 3: Variable Analysis       |
            |  (variables.py)                   |
            |                                   |
            |  Walks Pydantic model tree,       |
            |  builds scope chain, checks each  |
            |  variable reference resolves in   |
            |  current scope                    |
            |  Output: list[VariableIssue]      |
            +-----------------------------------+
                              |
                              v
                        AnalysisResult
```

Stage 2 operates on **raw YAML** (Python dicts/lists from `yaml.safe_load` or from the builder) to see literal `${...}` strings before Pydantic stores them as opaque `Any` values. Stage 3 operates on the **Pydantic model tree** to access typed step structures.

The builder pipeline (Layers 1-2-4) and validation pipeline (Layer 3) are **independent**. The builder produces raw dicts with no Pydantic involvement. Validation is opt-in via `analyze_workflow()` or `validate_workflow()`.

---

## Expression Parser

The expression parser handles GCP Workflows `${...}` expression syntax using a Pratt (top-down operator precedence) parser with optional error recovery.

### Token Types

| Category | Types | Examples |
|---|---|---|
| Literals | `INTEGER`, `DOUBLE`, `STRING` | `42`, `3.14`, `"hello"` |
| Keywords | `TRUE`, `FALSE`, `NULL`, `AND`, `OR`, `IN`, `NOT` | `true`, `and`, `not` |
| Identifiers | `IDENT` | `my_var`, `response`, `len` |
| Operators | `PLUS`, `MINUS`, `STAR`, `SLASH`, `PERCENT`, `EQ`, `NEQ`, `LT`, `LTE`, `GT`, `GTE` | `+`, `==`, `<=` |
| Delimiters | `LPAREN`, `RPAREN`, `LBRACKET`, `RBRACKET`, `LBRACE`, `RBRACE`, `DOT`, `COMMA`, `COLON` | `(`, `]`, `.` |
| End | `EOF` | -- |

### Lexing

Single-pass linear scan. At each position:

1. Skip whitespace
2. Try two-character operators (`==`, `!=`, `<=`, `>=`) before single-character ones
3. Single-character operators and delimiters via lookup table
4. String literals (double or single quoted, with backslash escapes)
5. Numbers (integer or double based on presence of `.`)
6. Identifiers / keywords (`[A-Za-z_][A-Za-z_0-9]*`, checked against keyword table)
7. Unrecognized character raises `LexError`

### Precedence Table

Lower rows bind tighter:

```
Precedence    Rule                Operators
1 (lowest)    or_expr             or
2             and_expr            and
3             membership          in
4             comparison          ==  !=  <  <=  >  >=
5             addition            +  -
6             multiplication      *  /  %
7             unary               - (prefix)
8             primary_postfix     .field  [index]  (args)
9 (highest)   primary             literals, identifiers, (expr), [list], {map}
```

### `not()` Handling

GCP Workflows uses function-call syntax for logical NOT: `not(x)` rather than `!x`. The parser accepts `not` as a primary value (like an identifier), then the postfix loop matches `(x)` as a function call. So `not(a and b)` parses as primary `not` + postfix call `(a and b)`.

### Error Recovery

`parse_expression_recover()` uses the same parser in recovery mode. When a parse error occurs, it inserts an `ErrorNode` and attempts to continue. Returns `(ast, errors)` where `errors` is a list of `ExpressionError`.

### `${...}` Extraction

`extract_expression_strings(value)` recursively walks any Python value tree and extracts expression bodies using brace-depth counting:

1. Scan for `${`
2. Track depth (increment on `{`, decrement on `}`, skip quoted strings)
3. Extract the substring between `${` and the matching `}`

This handles nested braces (`${ {"a": 1} }`) and strings containing braces.

---

## Variable Analysis

The variable analyzer (`variables.py`) walks the Pydantic model tree and maintains a scope chain to track variable definitions and references.

### Scope Chain

`Scope` is a linked list of symbol tables:

```
Workflow scope (params: name, age)
    |
    +-- For loop scope (value: item, index: idx)
    |
    +-- Try/except scope
            |
            +-- Except scope (as: e)
```

Each scope has `_vars` (dict of variable definitions), `parent` (enclosing scope), and `lookup(name)` (checks local then recurses to parent).

### Definition Sources

| Source | Kind | Scope |
|---|---|---|
| `params` | `PARAM` | Workflow root |
| `assign` step LHS | `ASSIGN` | Current scope |
| `result` on `call` | `RESULT` | Current scope |
| `result` on `try` call body | `RESULT` | Current scope |
| `for` value | `FOR_VALUE` | Child (loop) scope |
| `for` index | `FOR_INDEX` | Child (loop) scope |
| `except as` | `EXCEPT_AS` | Child (except) scope |

### Walk Order

Steps are walked top-to-bottom (sequential execution order). At each step:
1. Check all expression references (RHS of assigns, call args, conditions, return/raise values)
2. Define any new variables (LHS of assigns, result fields)

A variable referenced before its assign step is flagged as an error.

### Scoping Rules

- **Nested `steps:` blocks** do not create a new scope. Variables defined inside are visible outside. Matches GCP runtime behavior.
- **For loops** create a child scope. `value` and `index` variables are loop-local and cleared after the loop exits.
- **Except blocks** create a child scope. The `as` variable is only visible inside the except handler.
- **Parallel branches** each get their own child scope. Variables defined inside branches are not visible outside.

### Switch Branch Analysis

Each switch branch is analyzed independently. Variables defined in **all** branches get `Certainty.DEFINITE`. Variables defined in **some** branches get `Certainty.MAYBE`. References to `MAYBE` variables produce warnings (not errors).

### Subworkflow Name Exclusion

In Form B workflows, all subworkflow names are collected before analysis. Identifiers matching subworkflow names are skipped during variable reference checking (they are valid call targets, not variables).

### Root Variable Extraction

Nested access like `config.key1` or `items[0]` is treated as a modification of the root variable (`config`, `items`). Only the root is registered in scope. `extract_variable_references()` returns only root identifiers -- `response.body.data[0].name` yields `["response"]`. Built-in function names (`len`, `keys`, `int`, `double`, `string`, `bool`, `type`, `not`) followed by `(` are excluded.

---

## Project Structure

```
cloud-workflows-generator/
    pyproject.toml
    README.md
    REFERENCE.md
    ARCHITECTURE.md
    docs/
        01_overview.md          GCP Workflows top-level structure
        02_steps.md             Step type schemas
        03_error_handling.md    Try/except/retry/raise
        04_control_flow.md      Switch, for, parallel, jumps
        05_data_model.md        Variables, expressions, data types, functions
        06_pydantic_design.md   Pydantic model design spec (Layer 3)
        07_test_fixtures.md     YAML test examples and conventions
    src/cloud_workflows/
        __init__.py             Public API re-exports (72 symbols)
        steps.py                Layer 1+2: dict utilities + step classes
        builder.py              Layer 2+4: Steps container, _finalize(), build()
        retry.py                Layer 2: Retry + Backoff builder classes
        models.py               Layer 3: Pydantic v2 models + validate_workflow()
        expressions.py          Layer 3: Pratt parser for ${...} expressions
        variables.py            Layer 3: Scope-based variable tracking
        parser.py               Layer 3: analyze_yaml(), analyze_workflow()
        consts.py               Constants: stdlib functions, retry predicates
    tests/
        conftest.py             Shared test helpers
        test_consts.py          Constants tests
        validation/             YAML parsing + validation tests
            test_top_level.py
            test_assign.py
            test_call.py
            test_return_raise.py
            test_switch.py
            test_for.py
            test_parallel.py
            test_try.py
            test_nested.py
            test_expressions.py
            test_variables.py
            test_integration.py
        builder/                Workflow construction + CDK tests
            test_step_builder.py
            test_alias_methods.py
            test_workflow_builder.py
            test_cdk.py
            test_build.py
        fixtures/               YAML fixture files (100+ files, 15 directories)
            assign/
            build/
            call/
            cdk/
            expressions/
            for/
            integration/
            nested/
            parallel/
            return_raise/
            switch/
            top_level/
            try/
            variables/
```

## Running Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

569 tests: validation, CDK, builder (step builder + alias methods, workflow builder, build), constants.
