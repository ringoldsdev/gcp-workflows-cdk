# GCP Cloud Workflows Syntax Reference: Step Types

> Detailed schema for every step type. Each section shows the exact YAML structure,
> all fields, which are required/optional, value types, and constraints.
>
> **Convention**: `Any` means any valid Workflows value (string, number, boolean, null,
> list, map, or expression like `${...}`).

---

## 1. Assign Step

**Discriminating key**: `assign`

Sets one or more variables in a single step.

### Schema

```yaml
- STEP_NAME:
    assign:
      - VARIABLE_NAME_1: VALUE_1
      - VARIABLE_NAME_2: VALUE_2
      # ...up to 50 assignments
    next: NEXT_STEP  # optional
```

### Fields

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `assign` | `List[Dict[str, Any]]` | **Yes** | Min 1, **max 50** assignments per step |
| `next` | `str` | No | Step name, `end`, `break`, or `continue` |

### Assignment Entry

Each entry in the `assign` list is a **single-key dict**:
- Key: variable name (string). Can use dot notation (`my_map.key`) or bracket
  notation (`my_list[0]`, `my_map["key"]`).
- Value: any valid value or expression.

### Constraints
- **Maximum 50 assignments** per assign step.
- Assignments within one step are processed **sequentially** (top to bottom), so later
  assignments can reference variables set by earlier ones in the same step.

### Examples

```yaml
# Basic assignment
- assign_vars:
    assign:
      - number: 5
      - number_plus_one: ${number + 1}
      - string: "hello"
      - my_list: ["zero", "one", "two"]
      - my_map:
          name: "Alex"
          age: 30

# String concatenation across assignments (sequential processing)
- build_string:
    assign:
      - s: "say"
      - s: ${s + " hello"}
      - s: ${s + " to the world"}

# Map/list element assignment
- update_elements:
    assign:
      - my_map.key1: "value1"
      - my_map["key2"]: "value2"
      - my_list[0]: "updated"

# Clear a variable (set to null)
- clear:
    assign:
      - bigVar:
```

---

## 2. Call Step

**Discriminating key**: `call`

Invokes a function (HTTP method, standard library function, connector, or subworkflow)
and optionally stores the result.

### Schema

```yaml
- STEP_NAME:
    call: FUNCTION_NAME
    args:                    # optional
      ARG_1: VALUE_1
      ARG_2: VALUE_2
    result: OUTPUT_VARIABLE  # optional
    next: NEXT_STEP          # optional
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `call` | `str` | **Yes** | Function name (e.g. `http.get`, `sys.log`, `my_subworkflow`, `googleapis.compute.v1.instances.insert`) |
| `args` | `Dict[str, Any]` | No | Named arguments to pass to the function |
| `result` | `str` | No | Variable name to store the return value |
| `next` | `str` | No | Next step to execute |

### Call Targets

1. **HTTP methods**: `http.get`, `http.post`, `http.put`, `http.patch`, `http.delete`,
   `http.request`
2. **Standard library**: `sys.log`, `sys.sleep`, `sys.get_env`, `sys.now`,
   `sys.sleep_until`, `json.decode`, `json.encode`, etc.
3. **Connectors**: `googleapis.compute.v1.instances.insert`, etc.
4. **Subworkflows**: Any user-defined subworkflow name (e.g., `my_subworkflow`)
5. **Callbacks**: `events.create_callback_endpoint`, `events.await_callback`

### HTTP Call Args Structure

When calling HTTP functions (`http.get`, `http.post`, etc.), the `args` dict has these
known fields:

| Arg Field | Type | Required | Notes |
|-----------|------|----------|-------|
| `url` | `str` | **Yes** | The URL to call |
| `method` | `str` | For `http.request` only | HTTP method (GET, POST, etc.) |
| `headers` | `Dict[str, str]` | No | Request headers |
| `body` | `Any` | No | Request body (maps to JSON) |
| `query` | `Dict[str, Any]` | No | URL query parameters |
| `auth` | `Dict` | No | Authentication config |
| `timeout` | `number` | No | Timeout in seconds |

### Auth Sub-Structure

```yaml
auth:
    type: OIDC    # or "OAuth2"
```

### HTTP Response Structure

When stored in `result`, the HTTP response is a map with:
- `body` -- the response body
- `code` -- HTTP status code (integer)
- `headers` -- response headers (dict)

### Examples

```yaml
# Simple HTTP GET
- get_data:
    call: http.get
    args:
      url: https://example.com/api
    result: response

# HTTP POST with auth
- post_data:
    call: http.post
    args:
      url: https://us-central1-myproject.cloudfunctions.net/myfunc
      auth:
        type: OIDC
      body:
        message: "Hello World"
        count: 123
    result: the_message

# HTTP GET with headers and query params
- search:
    call: http.get
    args:
      url: https://en.wikipedia.org/w/api.php
      headers:
        Content-Type: "text/plain"
      query:
        action: opensearch
        search: monday
    result: wikiResult

# Standard library call
- log_it:
    call: sys.log
    args:
      data: ${wikiResult}

# Sleep
- wait:
    call: sys.sleep
    args:
      seconds: 10

# Call a subworkflow
- call_sub:
    call: name_message
    args:
      first_name: "Ada"
      last_name: "Lovelace"
    result: greeting

# Connector call
- insert_machine:
    call: googleapis.compute.v1.instances.insert
    args:
      project: ${projectID}
      zone: europe-west1-b
      body:
        name: my-machine
        machineType: zones/europe-west1-b/e2-small
```

---

## 3. Switch Step

**Discriminating key**: `switch`

Conditional branching. Evaluates conditions in order; the first one that evaluates to
`true` is executed.

### Schema

```yaml
- STEP_NAME:
    switch:
      - condition: ${EXPRESSION_A}
        next: TARGET_STEP_A        # action: jump
      - condition: ${EXPRESSION_B}
        steps:                     # action: embedded steps
          - nested_step:
              assign:
                - x: 1
      - condition: ${EXPRESSION_C}
        assign:                    # action: inline assign
          - y: 2
        next: TARGET_STEP_B
      - condition: ${EXPRESSION_D}
        return: VALUE              # action: return
      - condition: ${EXPRESSION_E}
        raise: ERROR_VALUE         # action: raise
      - condition: true            # default/fallthrough condition
        next: DEFAULT_STEP
    next: FALLTHROUGH_STEP         # optional: if no condition matches
```

### Fields

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `switch` | `List[SwitchCondition]` | **Yes** | Min 1, **max 50** conditions |
| `next` | `str` | No | Fallthrough: executed if no condition matches |

### SwitchCondition Structure

Each condition entry is a dict with:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `condition` | `str (expression)` | **Yes** | Must evaluate to boolean. Use `true` for default case. |
| `next` | `str` | No | Jump to step |
| `steps` | `List[Step]` | No | Embedded steps to execute |
| `assign` | `List[Dict[str, Any]]` | No | Inline variable assignments |
| `return` | `Any` | No | Return a value and stop |
| `raise` | `Any` | No | Raise an error |

**Action fields are mutually exclusive within a single condition** (you wouldn't combine
`return` and `next` in the same condition, for instance). However, `assign` + `next` can
co-exist in a condition (assign variables then jump).

### Constraints
- **Maximum 50 conditions** per switch block.
- Conditions are evaluated **in order**; the first `true` one wins.
- A `condition: true` serves as the default/catch-all and should be last.

### Examples

```yaml
# Basic switch with jumps
- check_value:
    switch:
      - condition: ${value < 10}
        next: small
      - condition: ${value < 100}
        next: medium
    next: large  # fallthrough if nothing matches

# Switch with embedded steps
- check_and_act:
    switch:
      - condition: ${a == 1}
        steps:
          - increment:
              assign:
                - a: ${a + 7}
          - done:
              return: ${"a is now " + string(a)}

# Switch with assign in condition
- check_input:
    switch:
      - condition: '${"searchTerm" in input}'
        assign:
          - searchTerm: ${input.searchTerm}
        next: readWikipedia

# Switch with return
- check_day:
    switch:
      - condition: ${day == "Friday"}
        return: "It's Friday!"
      - condition: ${day == "Saturday" or day == "Sunday"}
        return: "It's the weekend!"
    next: workday
```

---

## 4. Return Step

**Discriminating key**: `return`

Stops execution of the current workflow or subworkflow and returns a value.

### Schema

```yaml
- STEP_NAME:
    return: VALUE_OR_EXPRESSION
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `return` | `Any` | **Yes** | Value, variable reference, expression, map, or list |

### Value Forms

The return value can be:

```yaml
# Scalar expression
- done:
    return: ${my_variable}

# String literal
- done:
    return: "Something went wrong."

# Map (multiple values)
- done:
    return:
      field1: ${value1}
      field2: ${value2}

# List
- done:
    return:
      - ${workflowScope}
```

### Notes
- `return` **cannot** be used inside parallel branches or parallel for loop iterations.
  Use shared variables instead.
- `return` in a subworkflow returns control to the caller.
- `return` in `main` stops the entire workflow execution.

---

## 5. Raise Step

**Discriminating key**: `raise`

Raises a custom error that can be caught by a `try/except` block.

### Schema

```yaml
# String form
- STEP_NAME:
    raise: "Error message string"

# Expression form
- STEP_NAME:
    raise: ${error_variable}

# Map form
- STEP_NAME:
    raise:
      code: 55
      message: "Something went wrong."
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `raise` | `str \| Dict[str, Any] \| expression` | **Yes** | The error to raise |

### Value Forms

The raised value can be:
- **String literal**: `"Something went wrong."`
- **Expression**: `${e}` (re-raise a caught error)
- **Map**: `{code: 55, message: "..."}` with user-defined keys

---

## 6. Nested Steps Step

**Discriminating key**: `steps`

Groups a sequence of steps into a named block. Useful for organizing workflow logic and
required in certain contexts (inside `for` loops, `try` blocks, `except` blocks, `parallel`
branches, switch embedded steps).

### Schema

```yaml
- STEP_NAME:
    steps:
      - NESTED_STEP_1:
          ...
      - NESTED_STEP_2:
          ...
    next: NEXT_STEP  # optional
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `steps` | `List[Step]` | **Yes** | Ordered list of steps (recursive) |
| `next` | `str` | No | Next step after the block |

### Notes
- Variables declared inside a `steps` block have **workflow-level scope** (not block scope).
  They can be accessed outside of the block.
- Any step type can be nested inside a `steps` block: `assign`, `call`, `switch`, `for`,
  `parallel`, `try`, `return`, `raise`, `steps` (recursive nesting).

### Examples

```yaml
# Basic nested steps
- series_one:
    steps:
      - step_a:
          call: http.get
          args:
            url: https://host.com/api1
          result: api_response1
      - step_b:
          assign:
            - varA: "Monday"
            - varB: "Tuesday"
- series_two:
    steps:
      - step_c:
          call: http.get
          args:
            url: https://host.com/api2
          result: api_response2
```

---

## 7. For Step

**Discriminating key**: `for`

Iterates over a list, map keys, or numeric range.

### Schema (list iteration)

```yaml
- STEP_NAME:
    for:
      value: LOOP_VARIABLE       # required
      index: INDEX_VARIABLE      # optional
      in: ${LIST_EXPRESSION}     # required (mutually exclusive with range)
      steps:                     # required
        - INNER_STEP:
            ...
```

### Schema (range iteration)

```yaml
- STEP_NAME:
    for:
      value: LOOP_VARIABLE       # required
      range: ${[BEGIN, END]}     # required (mutually exclusive with in), both inclusive
      steps:                     # required
        - INNER_STEP:
            ...
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `for` | `ForBody` | **Yes** | Contains the loop definition |

### ForBody Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `value` | `str` | **Yes** | Loop variable name (current element) |
| `index` | `str` | No | Index variable (0-based offset). Only valid with `in`, not `range`. |
| `in` | `Any (expression or list)` | **Yes*** | List to iterate. *Mutually exclusive with `range`. |
| `range` | `List[number, number]` or expression | **Yes*** | `[begin, end]` inclusive. *Mutually exclusive with `in`. |
| `steps` | `List[Step]` | **Yes** | Steps to execute each iteration |

### Constraints & Rules
- `in` and `range` are **mutually exclusive** -- exactly one must be present.
- `range` values are **inclusive** on both ends: `range: [1, 9]` produces 9 iterations
  (1, 2, 3, 4, 5, 6, 7, 8, 9).
- If `END < BEGIN` in range, the loop has **0 iterations** (no error).
- Range increments by 1 (or 1.0 for doubles) each iteration.
- Negative values are allowed: `range: [-10, -1]` = 10 iterations.
- Floating-point values are allowed and **not** rounded: `range: [-1.1, -1]` = 1 iteration.
- **Do not** use `[${rangeStart}, ${rangeEnd}]`. Use `${[rangeStart, rangeEnd]}` instead.
- Loop variables (`value`, `index`) have **loop-local scope** -- they are cleared after
  the loop exits. Accessing them outside raises a deployment error.
- The order of `value`, `index`, `in`/`range`, `steps` within the `for` block does not matter.
- You can use `next: break` to exit the loop or `next: continue` to skip to the next
  iteration (from within the steps).
- Jumping between named steps is only allowed **within the same loop**. Jumping in/out
  of a loop or between loops is not allowed.

### Examples

```yaml
# List iteration
- loopList:
    for:
      value: v
      in: ${list}
      steps:
        - sum:
            assign:
              - total: ${total + v}

# Map iteration
- loopMap:
    for:
      value: key
      in: ${keys(map)}
      steps:
        - process:
            assign:
              - total: ${total + map[key]}

# Range iteration
- loopRange:
    for:
      value: v
      range: [1, 9]
      steps:
        - sum:
            assign:
              - total: ${total + v}

# With index
- loopWithIndex:
    for:
      value: item
      index: i
      in: ${my_list}
      steps:
        - log:
            call: sys.log
            args:
              text: ${"Item " + string(i) + ": " + string(item)}
```

---

## 8. Parallel Step

**Discriminating key**: `parallel`

Executes steps concurrently, either via named **branches** or a parallel **for** loop.

### Schema (branches form)

```yaml
- STEP_NAME:
    parallel:
      exception_policy: POLICY          # optional
      shared: [VAR_A, VAR_B, ...]      # optional
      concurrency_limit: LIMIT          # optional
      branches:
        - BRANCH_A:
            steps:
              - ...
        - BRANCH_B:
            steps:
              - ...
```

### Schema (parallel for form)

```yaml
- STEP_NAME:
    parallel:
      exception_policy: POLICY          # optional
      shared: [VAR_A, VAR_B, ...]      # optional
      concurrency_limit: LIMIT          # optional
      for:
        value: LOOP_VAR
        in: ${LIST}      # or range: [BEGIN, END]
        steps:
          - ...
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `parallel` | `ParallelBody` | **Yes** | Contains branches or for loop |

### ParallelBody Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `exception_policy` | `str` | No | Only `"continueAll"` is supported. Default behavior. |
| `shared` | `List[str]` | No | Variables from parent scope to allow write access |
| `concurrency_limit` | `int \| expression` | No | Max concurrent branches/iterations. Positive integer. |
| `branches` | `List[Branch]` | **Yes*** | *Mutually exclusive with `for` |
| `for` | `ForBody` | **Yes*** | *Mutually exclusive with `branches` |

### Constraints
- `branches` and `for` are **mutually exclusive** -- exactly one must be present.
- **Branches**: minimum **2**, maximum **10** branches.
- Each branch is a single-key dict with key = branch name, value = object with `steps` field.
- `shared` variables: only needed for variables that will be **written** to from within
  parallel branches/iterations. Read-only variables from parent scope are accessible
  without `shared`.
- `return` is **not allowed** inside parallel branches or iterations. Use shared variables
  to pass values out.
- `concurrency_limit` applies only to the immediate parallel step, not to nested
  parallel steps.
- Nested parallel steps can exist up to a platform depth limit.

### Branch Structure

```yaml
- BRANCH_NAME:
    steps:
      - STEP_A:
          ...
      - STEP_B:
          ...
```

### Examples

```yaml
# Parallel branches
- parallel_work:
    parallel:
      shared: [user, notification]
      branches:
        - getUser:
            steps:
              - call:
                  call: http.get
                  args:
                    url: ${"https://example.com/users/" + userId}
                  result: user
        - getNotification:
            steps:
              - call:
                  call: http.get
                  args:
                    url: ${"https://example.com/notifications/" + notifId}
                  result: notification

# Parallel for loop
- parallel_loop:
    parallel:
      shared: [total]
      for:
        value: postId
        in: ${posts}
        steps:
          - getCount:
              call: http.get
              args:
                url: ${"https://example.com/comments/" + postId}
              result: count
          - add:
              assign:
                - total: ${total + count}

# With concurrency limit
- limited_parallel:
    parallel:
      concurrency_limit: 2
      for:
        range: [1, 3]
        value: i
        steps:
          - work:
              call: http.get
              args:
                url: "https://example.com/work"
```

---

## 9. Try Step

**Discriminating key**: `try`

Defines error handling with optional retry and exception catching. Detailed in
[03_error_handling.md](./03_error_handling.md).

### Schema (brief)

```yaml
- STEP_NAME:
    try:
      # Single call form:
      call: http.get
      args:
        url: https://example.com
      result: response
      # OR multi-step form:
      steps:
        - step_a:
            ...
        - step_b:
            ...
    retry: RETRY_POLICY     # optional
    except:                 # optional
      as: ERROR_VAR
      steps:
        - handle:
            ...
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `try` | `TryBody` | **Yes** | Single call or steps block |
| `retry` | `RetryPolicy` | No | String expression or config object |
| `except` | `ExceptBody` | No | Error handler |

See [03_error_handling.md](./03_error_handling.md) for full details.

---

## Step Type Discrimination Summary

When parsing a step body dict, determine the type by checking for these keys **in order**:

1. Has `try` key -> **TryStep** (may also have `retry`, `except`)
2. Has `parallel` key -> **ParallelStep**
3. Has `for` key -> **ForStep**
4. Has `switch` key -> **SwitchStep** (may also have `next`)
5. Has `call` key -> **CallStep** (may also have `args`, `result`, `next`)
6. Has `assign` key -> **AssignStep** (may also have `next`)
7. Has `return` key -> **ReturnStep**
8. Has `raise` key -> **RaiseStep**
9. Has `steps` key -> **NestedStepsStep** (may also have `next`)

This ordering handles cases where multiple keys could theoretically appear, though in
practice each step has exactly one discriminating key (plus optional `next`).
