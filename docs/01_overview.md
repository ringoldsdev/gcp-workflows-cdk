# GCP Cloud Workflows Syntax Reference: Overview

> **Purpose**: This document (and its sibling files) is the single source of truth for
> implementing a Pydantic v2 YAML validator for Google Cloud Workflows. A new session
> should be able to read these docs and implement everything without re-crawling GCP docs.
>
> Source: https://cloud.google.com/workflows/docs/reference/syntax

---

## 1. File Format

- A workflow source file is **either valid YAML or valid JSON**.
- It contains **exactly one** main workflow.
- It **may** contain zero or more subworkflows.
- YAML indentation must be **at least 2 spaces** per level. Insufficient indentation
  causes errors. A new level must be at least 2 spaces from the *start of the text* on
  the previous line.

---

## 2. Top-Level Structure (Polymorphic Root)

The YAML document root can take **two mutually exclusive forms**:

### Form A: Simple Workflow (flat list of steps)

When there are **no subworkflows** and **no runtime arguments**, the top-level document is
a flat ordered list of steps:

```yaml
- step_one:
    assign:
      - message: "hello"
- step_two:
    return: ${message}
```

In Python/Pydantic terms: `List[Step]`

### Form B: Workflow with `main` block (dict of workflow definitions)

When there are subworkflows, runtime arguments, or both, the top-level document is a
**dict** where:
- The key `main` is **required** and maps to a workflow definition.
- Additional keys are **subworkflow names**, each mapping to a workflow definition.

```yaml
main:
    params: [args]
    steps:
        - call_sub:
            call: my_subworkflow
            args:
                name: ${args.name}
            result: greeting
        - done:
            return: ${greeting}

my_subworkflow:
    params: [name]
    steps:
        - prepare:
            return: ${"Hello " + name}
```

In Python/Pydantic terms: `Dict[str, WorkflowDefinition]`

### WorkflowDefinition Structure

Each workflow definition (main or subworkflow) has:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `params` | `List[str \| Dict[str, Any]]` | No | See params rules below |
| `steps` | `List[Step]` | **Yes** | Ordered list of named steps |

---

## 3. Params Rules

### In `main`

- `main` accepts **exactly one** parameter (a single name).
- That parameter receives the entire runtime argument payload (typically a JSON object).
- You then use dot notation to access fields: `${args.firstName}`.

```yaml
main:
    params: [args]
    steps:
        - step1:
            return: ${args.firstName}
```

### In subworkflows

- Subworkflows can accept **multiple** parameters.
- Parameters are enclosed in square brackets: `params: [param1, param2, param3]`
- Parameters can have **default values** using the `name: default_value` syntax:

```yaml
my_subworkflow:
    params: [first_name, last_name, country: "England"]
    steps:
        - greet:
            return: ${"Hello " + first_name + " " + last_name + " from " + country}
```

### Params Entry Types (Polymorphic)

Each entry in the `params` list is one of:
- **Plain string**: `"param_name"` -- required parameter, no default
- **Single-key dict**: `{"param_name": default_value}` -- optional parameter with default

In JSON representation, the default-value form is explicit:
```json
"params": ["Street", "ZipCode", {"Country": "United States"}]
```

---

## 4. Steps: General Structure

A **step** is a single-key dict where:
- The **key** is the step name (string, unique within its subworkflow scope)
- The **value** is the step body (a dict whose keys determine the step type)

```yaml
- my_step_name:
    assign:
      - x: 5
```

### Step Name Rules
- Must be unique at the subworkflow level (but the same name can appear in different
  subworkflows or in `main` vs a subworkflow).
- Recommended: alphanumeric characters and underscores only.
- No enforced naming convention by Workflows itself.

### Step Execution Order
- By default, steps execute **sequentially** in the order they appear.
- The `next` field can override this to jump to any step in the same scope.

---

## 5. The `next` Field (Cross-Cutting)

The `next` field can appear on **any** step type as an optional field. It controls which
step executes after the current one completes.

```yaml
- my_step:
    assign:
      - x: 5
    next: some_other_step
```

Special `next` values:
- **`end`**: Stop execution of the current workflow/subworkflow. Returns `null`.
- **`break`**: Terminate the current `for` loop (only valid inside a `for` loop).
- **`continue`**: Skip to the next iteration of the current `for` loop (only valid inside
  a `for` loop).
- **Any step name**: Jump to that step (must be in the same scope).

---

## 6. Reserved Keywords

These are all the reserved words in the Workflows syntax. They cannot be used as variable
names or step names in contexts where they would be ambiguous:

| Keyword | Purpose |
|---------|---------|
| `args` | Pass arguments to a function call |
| `assign` | Set variable values |
| `branches` | Define parallel branches |
| `break` | Terminate a for loop |
| `call` | Run a function/subworkflow |
| `condition` | Boolean expression in switch cases |
| `continue` | Skip to next for loop iteration |
| `end` | Stop execution without returning |
| `except` | Catch errors from try block |
| `for` | Iterate over a list or range |
| `main` | Define the main workflow |
| `next` | Define the next step to execute |
| `parallel` | Execute steps concurrently |
| `params` | Accept workflow/subworkflow parameters |
| `raise` | Raise a custom error |
| `result` | Store function call return value |
| `retry` | Define retry behavior |
| `return` | Stop execution and return a value |
| `shared` | Mark variables as writable in parallel steps |
| `steps` | Nest a series of steps |
| `switch` | Conditional branching |
| `try` | Define steps to retry or catch errors for |

---

## 7. Complete List of Step Types

Every step body is identified by the **presence of specific keys**. These are the step
types and their discriminating keys:

| Step Type | Discriminating Key | Other Possible Keys | Notes |
|-----------|--------------------|---------------------|-------|
| **assign** | `assign` | `next` | Variable assignment |
| **call** | `call` | `args`, `result`, `next` | Function/HTTP/subworkflow call |
| **switch** | `switch` | `next` | Conditional branching |
| **for** | `for` | (none at step level) | Iteration |
| **parallel** | `parallel` | (none at step level) | Concurrent execution |
| **try** | `try` | `retry`, `except` | Error handling |
| **raise** | `raise` | (none) | Raise an error |
| **return** | `return` | (none) | Return a value and stop |
| **steps** (nested) | `steps` | `next` | Group steps into a block |

**Important discrimination rules:**
- A step body contains **exactly one** discriminating key (you cannot have both `assign`
  and `call` in the same step, for example).
- The `next` field is the exception -- it can co-exist with `assign`, `call`, `switch`,
  or `steps`.
- `try` can co-exist with `retry` and/or `except` (they are part of the try construct).

---

## Next Files

- [02_steps.md](./02_steps.md) -- Detailed schema for each step type
- [03_error_handling.md](./03_error_handling.md) -- try/except/retry/raise details
- [04_control_flow.md](./04_control_flow.md) -- switch, jumps, for loops, parallel
- [05_data_model.md](./05_data_model.md) -- Variables, expressions, data types
- [06_pydantic_design.md](./06_pydantic_design.md) -- Pydantic model design specification
- [07_test_fixtures.md](./07_test_fixtures.md) -- YAML test examples
