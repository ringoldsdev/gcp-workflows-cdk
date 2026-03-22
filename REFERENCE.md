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
| `workflow.to_dict()` | Serialize to Python dict/list (method on `SimpleWorkflow`/`SubworkflowsWorkflow`) |
| `workflow.to_yaml()` | Serialize to YAML string (method on `SimpleWorkflow`/`SubworkflowsWorkflow`) |

### Analysis

| Function | Description |
|---|---|
| `analyze_yaml(yaml_str)` | Parse YAML + validate expressions + analyze variables. Returns `AnalysisResult` |
| `analyze_workflow(workflow)` | Same as `analyze_yaml` but takes a model (no YAML round-trip) |

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

`Steps` is the universal container for workflow steps. Steps are added via the `__call__` protocol.

```python
s = Steps()
s("step_id", StepType)      # add a named step (returns None)
s(other_steps)               # merge steps from another Steps container
s.build() -> list[dict]      # serialize to list of step dicts
s._finalize() -> Workflow    # convert to SimpleWorkflow or SubworkflowsWorkflow
```

| Method | Description |
|---|---|
| `s("name", step)` | Add a named step. `step` must be a `StepType` instance. Returns `None`. |
| `s(other)` | Merge all steps from another `Steps` instance (appends in order). |
| `s.build()` | Serialize to `list[dict]` — each entry is `{step_id: body}`. |
| `s._finalize()` | Convert to a Pydantic workflow model (`SimpleWorkflow` or `SubworkflowsWorkflow`). |
| `len(s)` | Number of steps. |

Constructor:

```python
Steps(*, params=None)
```

| Arg | Description |
|---|---|
| `params` | Optional `list` of parameter names (strings) or parameter dicts with defaults (e.g. `[{"timeout": 30}]`). When set, the container represents a subworkflow. |

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
Switch(conditions, *, next=None)
```

| Arg | Description |
|---|---|
| `conditions` | List of `Condition` objects (at least one required). |
| `next` | Default fallthrough target. |

#### Condition

```python
Condition(condition, *, next=None, steps=None, assign=None, return_=UNSET, raise_=UNSET)
```

| Arg | Description |
|---|---|
| `condition` | The condition expression. |
| `next` | Jump target. |
| `steps` | Inline `Steps` container to execute. |
| `assign` | Inline assignments (list of single-key dicts). |
| `return_` | Return value if condition is true. Uses `_UNSET` sentinel; `None` is a valid value. |
| `raise_` | Raise value if condition is true. Uses `_UNSET` sentinel; `None` is a valid value. |

#### For

```python
For(*, value, in_=None, range=None, index=None, steps)
```

| Arg | Description |
|---|---|
| `value` | Loop variable name (required). |
| `in_` | Collection to iterate (mutually exclusive with `range`). |
| `range` | Range specification `[start, end]` or `[start, end, step]`. |
| `index` | Optional index variable name. |
| `steps` | Loop body — `Steps` container or list of dicts (required). |

#### Parallel

```python
Parallel(*, branches, shared=None, exception_policy=None, concurrency_limit=None)
```

| Arg | Description |
|---|---|
| `branches` | Dict of `{name: Steps}` (at least one required). |
| `shared` | List of shared variable names. |
| `exception_policy` | Exception handling policy (e.g. `"continueAll"`). |
| `concurrency_limit` | Max concurrent branches. |

#### Try

```python
Try(*, steps, retry=None, except_=None)
```

| Arg | Description |
|---|---|
| `steps` | Try body — `Steps` container or list of dicts (required). |
| `retry` | Retry config — dict, `RetryConfig` model, or string predicate name. |
| `except_` | Except handler — dict with `"as"` and `"steps"` keys, or `ExceptBody` model. |

Try body auto-detection: if the body is a single Call step, it produces a `TryCallBody` (flat call fields); otherwise a `TryStepsBody` (nested steps list).

Retry dict format:

```python
{
    "predicate": "http.default_retry",    # or an expression
    "max_retries": 3,
    "backoff": {
        "initial_delay": 1,
        "max_delay": 60,
        "multiplier": 2,
    },
}
```

#### NestedSteps

```python
NestedSteps(*, steps, next=None)
```

| Arg | Description |
|---|---|
| `steps` | Nested `Steps` container or list of dicts. |
| `next` | Jump target step name. |

### build() Function

```python
build(workflows: dict[str, Steps | dict[str, Steps] | Workflow], output_dir: str | Path = ".") -> list[Path]
```

Writes each `{filename: workflow}` entry as a YAML file to `output_dir`. Creates directories as needed. Returns the list of written file paths.

Values can be:

| Type | Behavior |
|---|---|
| `Steps` | Auto-finalized. No params → `SimpleWorkflow`; with params → `SubworkflowsWorkflow`. |
| `dict[str, Steps]` | Multi-workflow. Assembled into `SubworkflowsWorkflow`. Single `"main"` without params collapses to `SimpleWorkflow`. |
| `SimpleWorkflow` / `SubworkflowsWorkflow` | Passed through directly. |

### Composition

Steps containers are composable via the merge protocol:

```python
common = Steps()
common("log", Call("sys.log", args={"text": "starting"}))

main = Steps()
main(common)                # merges steps from common
main("done", Return("ok"))
```

Factory functions that return `Steps` instances are the primary composition pattern:

```python
def logging_steps(message):
    s = Steps()
    s("log", Call("sys.log", args={"text": message}))
    return s

main = Steps()
main("init", Assign(status="starting"))
main(logging_steps("Workflow started"))
main("done", Return("ok"))
```

---

## Pydantic Models

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
| `ReturnStep(return_: Any)` | `return` | — |
| `RaiseStep(raise_: Any)` | `raise` | — |
| `SwitchStep(switch: list[SwitchCondition])` | `switch` | `next` (fallthrough) |
| `ForStep(for_: ForBody)` | `for` | — |
| `ParallelStep(parallel: ParallelBody)` | `parallel` | — |
| `TryStep(try_: TryBody)` | `try` | `retry`, `except_` |
| `NestedStepsStep(steps: list[Step])` | `steps` | `next` |

### Supporting Models

| Model | Fields |
|---|---|
| `SwitchCondition` | `condition`, `next?`, `steps?`, `assign?`, `return_?`, `raise_?` |
| `ForBody` | `value`, `in_?` (mutually exclusive with `range`), `range?`, `index?`, `steps` |
| `ParallelBody` | `branches?` (mutually exclusive with `for_`), `for_?`, `shared?`, `exception_policy?`, `concurrency_limit?` |
| `Branch(name, steps)` | Single-key dict serialization |
| `TryCallBody(call, args?, result?)` | Try body form A |
| `TryStepsBody(steps)` | Try body form B |
| `ExceptBody(as_, steps)` | Except handler |
| `RetryConfig(predicate, max_retries, backoff)` | Custom retry configuration |
| `BackoffConfig(initial_delay, max_delay, multiplier)` | Exponential backoff settings |

### Validation Constraints

- `AssignStep.assign`: 1-50 entries, each must be a single-key dict
- `SwitchStep.switch`: 1-50 conditions
- `ParallelBody.branches`: 2-10 branches
- `ForBody`: exactly one of `in_` or `range` must be set
- `ParallelBody`: exactly one of `branches` or `for_` must be set

### Field Aliases

Python reserved words use trailing underscores as field names. Pydantic aliases handle YAML serialization:

| Field | Alias |
|---|---|
| `return_` | `return` |
| `raise_` | `raise` |
| `for_` | `for` |
| `in_` | `in` |
| `as_` | `as` |
| `except_` | `except` |
| `try_` | `try` |

---

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full builder pipeline, step class design, and validation pipeline diagrams.

### Module Map

```
src/cloud_workflows/
    __init__.py       Public API re-exports
    models.py         Pydantic v2 models + serialization
    expressions.py    Pratt parser for ${...} expressions
    variables.py      Scope-based variable tracking
    parser.py         Analysis pipeline (analyze_yaml, analyze_workflow)
    builder.py        Steps container + build() function
    steps.py          StepType base + step classes (Assign, Call, Switch, etc.)
```

### Processing Pipeline

`analyze_yaml(yaml_str)` and `analyze_workflow(workflow)` run three stages:

```
                  YAML string / Workflow model
                              |
                              v
            +-----------------------------------+
            |  Stage 1: Structural Validation   |
            |  (models.py -- Pydantic v2)       |
            |                                   |
            |  yaml.safe_load() + Pydantic      |
            |  model validation: types, field   |
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

Stage 2 operates on **raw YAML** (Python dicts/lists from `yaml.safe_load`) to see literal `${...}` strings before Pydantic stores them as opaque `Any` values. Stage 3 operates on the **Pydantic model tree** to access typed step structures.

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
        06_pydantic_design.md   Pydantic model design spec
        07_test_fixtures.md     YAML test examples and conventions
    src/cloud_workflows/
        __init__.py             Public API re-exports
        models.py               Pydantic v2 models + serialization
        expressions.py          Pratt parser for ${...} expressions
        variables.py            Scope-based variable tracking
        parser.py               Analysis pipeline functions
        builder.py              Steps container + build() function
        steps.py                StepType base + step classes
    tests/
        conftest.py             Shared test helpers
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
            test_workflow_builder.py
            test_cdk.py
            test_build.py
        fixtures/               YAML fixture files (95 files, 14 directories)
            assign/
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

390 tests: 304 validation/CDK + 86 builder (step builder + workflow builder + build).
