# GCP Cloud Workflows Syntax Reference: Control Flow

> Detailed reference for switch conditions, jumps, iteration (for loops), and parallel
> execution. This supplements the structural schemas in `02_steps.md` with behavioral
> details and edge cases.
>
> Source: https://cloud.google.com/workflows/docs/reference/syntax/conditions,
> https://cloud.google.com/workflows/docs/reference/syntax/jumps,
> https://cloud.google.com/workflows/docs/reference/syntax/iteration,
> https://cloud.google.com/workflows/docs/reference/syntax/parallel-steps

---

## 1. Switch / Conditions

### Overview

A `switch` step evaluates conditions in order. The first condition that evaluates to
`true` has its associated action executed. If no condition matches and a fallthrough
`next` is present on the outer switch, that step runs. Otherwise, execution continues
to the next sequential step.

### Condition Expressions

The `condition` field contains an expression that evaluates to a boolean:

```yaml
condition: ${x > 10}
condition: ${name == "Alice"}
condition: ${"key" in my_map}
condition: ${x > 0 and x < 100}
condition: ${not(is_done)}
condition: true   # catch-all / default
```

### Supported Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `${x == 5}` |
| `!=` | Not equal | `${x != 5}` |
| `<` | Less than | `${x < 10}` |
| `<=` | Less or equal | `${x <= 10}` |
| `>` | Greater than | `${x > 10}` |
| `>=` | Greater or equal | `${x >= 10}` |

### Supported Logical Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `and` | Logical AND | `${x > 0 and x < 100}` |
| `or` | Logical OR | `${x < 0 or x > 100}` |
| `not()` | Logical NOT | `${not(is_done)}` |

### Membership / Containment

```yaml
# Check if key exists in a map
condition: '${"searchTerm" in args}'

# Check if value exists in a list
condition: ${item in my_list}
```

### SwitchCondition Action Fields

Each condition can have **one primary action** (some can combine):

| Action | Type | Description |
|--------|------|-------------|
| `next` | `str` | Jump to named step |
| `steps` | `List[Step]` | Execute embedded steps |
| `assign` | `List[Dict[str, Any]]` | Inline assignments |
| `return` | `Any` | Return a value |
| `raise` | `Any` | Raise an error |

**Combinability rules:**
- `assign` + `next` can coexist (assign variables, then jump)
- `steps` is standalone (cannot combine with `next`, `return`, `raise`)
- `return` is standalone
- `raise` is standalone
- `next` alone is valid (just jump)
- A condition with no action fields but just `condition: true` is valid as a no-op default

### Outer Fallthrough `next`

The `next` field on the switch step itself (not on a condition) executes if **no
condition matches**:

```yaml
- check:
    switch:
      - condition: ${x < 0}
        next: handle_negative
      - condition: ${x > 100}
        next: handle_overflow
    next: handle_normal  # fallthrough
```

### Constraints

- **Maximum 50 conditions** per switch step.
- Conditions are evaluated **in order**; first match wins.
- A `condition: true` entry serves as a default and should be the last entry.

---

## 2. Jumps (the `next` field)

### Overview

The `next` field controls which step executes after the current one. Without `next`,
steps execute sequentially.

### Placement

`next` can appear on these step types:
- **assign** step
- **call** step
- **switch** step (outer fallthrough)
- **switch condition** entries (per-condition jump)
- **nested steps** step

### Special Values

| Value | Description | Valid Context |
|-------|-------------|---------------|
| `end` | Stop execution of current workflow/subworkflow, return `null` | Anywhere |
| `break` | Exit the current `for` loop | Inside a `for` loop only |
| `continue` | Skip to next iteration of the current `for` loop | Inside a `for` loop only |
| *step_name* | Jump to named step in the same scope | Same subworkflow/scope |

### Jump Scope Rules

- Jumps can only target steps **within the same scope** (same subworkflow, same for loop
  body, same parallel branch).
- You **cannot** jump into or out of a `for` loop body.
- You **cannot** jump into or out of a `parallel` branch.
- You **cannot** jump between different parallel branches.
- You **can** jump between steps within the same for loop body.
- You **can** jump between steps at the top level of a subworkflow.

### Jump Examples

```yaml
# Jump to a specific step
- step_one:
    assign:
      - x: 1
    next: step_three

- step_two:
    assign:
      - x: 2  # skipped by the jump above

- step_three:
    return: ${x}  # returns 1
```

```yaml
# End execution early
- check_done:
    switch:
      - condition: ${is_complete}
        next: end
    next: continue_work
```

```yaml
# Break and continue in for loops
- loop:
    for:
      value: item
      in: ${items}
      steps:
        - check:
            switch:
              - condition: ${item == null}
                next: continue  # skip null items
              - condition: ${item == "STOP"}
                next: break     # exit the loop
        - process:
            assign:
              - results: ${list.concat(results, [item])}
```

---

## 3. For Loops (Iteration)

### Overview

For loops iterate over lists, map keys, or numeric ranges. The loop body is a `steps`
block.

### List Iteration

```yaml
- loop:
    for:
      value: item
      in: ${my_list}
      steps:
        - process:
            assign:
              - total: ${total + item}
```

### Map Iteration

Iterate over map keys using the `keys()` function:

```yaml
- loop:
    for:
      value: key
      in: ${keys(my_map)}
      steps:
        - process:
            assign:
              - total: ${total + my_map[key]}
```

### Range Iteration

```yaml
- loop:
    for:
      value: i
      range: [1, 10]  # inclusive both ends: 1,2,3,...,10
      steps:
        - log:
            call: sys.log
            args:
              text: ${string(i)}
```

### Index Variable

Only valid with `in` (not `range`):

```yaml
- loop:
    for:
      value: item
      index: idx
      in: ${my_list}
      steps:
        - log:
            call: sys.log
            args:
              text: ${"Item " + string(idx) + ": " + string(item)}
```

### Key Constraints

1. `in` and `range` are **mutually exclusive** -- exactly one must be present
2. `index` is only valid with `in`, not with `range`
3. Range is **inclusive on both ends**: `[1, 5]` = 5 iterations (1, 2, 3, 4, 5)
4. If `END < BEGIN`, range produces **0 iterations** (no error)
5. Negative and float values allowed in range
6. Use `${[start, end]}` not `[${start}, ${end}]` for dynamic ranges
7. Loop variables (`value`, `index`) have **loop-local scope** -- they are cleared after
   the loop exits
8. `next: break` exits the loop; `next: continue` skips to next iteration
9. Jumps within a loop body are restricted to the same loop body scope

### Nested For Loops

For loops can be nested. Each loop has its own scope for `value`/`index` variables:

```yaml
- outer:
    for:
      value: row
      in: ${matrix}
      steps:
        - inner:
            for:
              value: cell
              in: ${row}
              steps:
                - process:
                    assign:
                      - total: ${total + cell}
```

---

## 4. Parallel Execution

### Overview

The `parallel` step executes work concurrently. It has two mutually exclusive forms:
**branches** (named concurrent branches) and **for** (parallel iteration).

### Branches Form

Each branch is a named block containing `steps`:

```yaml
- work:
    parallel:
      shared: [results]
      branches:
        - branch_a:
            steps:
              - get_a:
                  call: http.get
                  args:
                    url: https://api.example.com/a
                  result: a_result
              - save_a:
                  assign:
                    - results: ${list.concat(results, [a_result.body])}
        - branch_b:
            steps:
              - get_b:
                  call: http.get
                  args:
                    url: https://api.example.com/b
                  result: b_result
              - save_b:
                  assign:
                    - results: ${list.concat(results, [b_result.body])}
```

### Parallel For Form

```yaml
- process_all:
    parallel:
      shared: [total]
      for:
        value: item
        in: ${items}
        steps:
          - process:
              call: http.post
              args:
                url: https://api.example.com/process
                body: ${item}
              result: response
          - accumulate:
              assign:
                - total: ${total + response.body.count}
```

### Shared Variables

- `shared` declares variables from the parent scope that branches/iterations may **write**.
- Variables in parent scope can be **read** without `shared`.
- `shared` is only needed for **write access**.
- Race conditions are possible: if multiple branches write to the same shared variable,
  the final value is nondeterministic.

### Exception Policy

```yaml
parallel:
  exception_policy: continueAll
```

- `"continueAll"` is the **only** supported value.
- When set, if one branch/iteration fails, other branches continue executing.
  The error is collected and raised after all branches complete.
- Without `exception_policy`, the default behavior is that an unhandled error in any
  branch causes other branches to be cancelled.

### Concurrency Limit

```yaml
parallel:
  concurrency_limit: 5
```

- Limits the maximum number of branches/iterations running concurrently.
- Must be a positive integer or expression evaluating to one.
- Applies only to the immediate parallel step (not nested).
- Default: no limit (all branches/iterations run concurrently).

### Branch Constraints

- Minimum **2** branches, maximum **10** branches.
- Each branch is a single-key dict: `{branch_name: {steps: [...]}}`.
- Branch names must be unique within the parallel step.

### Parallel Restrictions

- `return` is **not allowed** inside parallel branches or parallel for iterations.
  Use shared variables to pass data out.
- Nested parallel steps are allowed but have a platform depth limit.
- Jumps cannot cross parallel branch boundaries.
- Each branch has its own scope for locally declared variables; only `shared` variables
  are visible across branches.

---

## 5. Control Flow Summary for Validator

### Validation Rules to Enforce

| Rule | Location | Error |
|------|----------|-------|
| Max 50 conditions | `switch` | Too many switch conditions |
| `in` XOR `range` in for | `for` body | Mutually exclusive fields |
| `index` only with `in` | `for` body | Index not valid with range |
| `branches` XOR `for` in parallel | `parallel` body | Mutually exclusive fields |
| 2-10 branches | `parallel.branches` | Invalid branch count |
| `exception_policy` only `"continueAll"` | `parallel` | Invalid policy value |
| `concurrency_limit` positive int | `parallel` | Invalid limit |
| `break`/`continue` only inside for loop | `next` field | Invalid next value |

### Step-Level `next` Validity

The validator should accept `next` on: assign, call, switch, nested steps.
The validator should NOT expect `next` on: return, raise, for, parallel, try.
(Though `for` and `parallel` and `try` have `next`-like control flow inside their bodies.)
