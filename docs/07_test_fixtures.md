# YAML Test Fixtures for Cloud Workflows Validator

> Test examples for the pytest test suite. Each fixture is a complete YAML document
> with metadata about what it tests and whether it should pass or fail validation.
>
> **Convention**: `# VALID` = should parse without errors. `# INVALID` = should raise
> `ValidationError`.

---

## 1. Top-Level Structure Tests

### 1.1 Form A: Simple Workflow (VALID)

```yaml
# test_form_a_simple.yaml
# VALID - Form A: flat list of steps
- assign_vars:
    assign:
      - message: "hello"
- return_result:
    return: ${message}
```

### 1.2 Form B: Workflow with Main (VALID)

```yaml
# test_form_b_main.yaml
# VALID - Form B: dict with main block
main:
    params: [args]
    steps:
        - step1:
            return: ${args.name}
```

### 1.3 Form B: Main + Subworkflow (VALID)

```yaml
# test_form_b_subworkflow.yaml
# VALID - Form B with main and subworkflow
main:
    params: [args]
    steps:
        - call_sub:
            call: greet
            args:
                name: ${args.name}
            result: greeting
        - done:
            return: ${greeting}

greet:
    params: [name]
    steps:
        - build:
            return: ${"Hello, " + name}
```

### 1.4 Form B: Missing Main (INVALID)

```yaml
# test_form_b_no_main.yaml
# INVALID - Form B must have 'main' key
my_subworkflow:
    params: [x]
    steps:
        - step1:
            return: ${x}
```

### 1.5 Form B: Params with Defaults (VALID)

```yaml
# test_params_defaults.yaml
# VALID - Subworkflow params with default values
main:
    steps:
        - call_sub:
            call: my_sub
            args:
                first: "Alice"
            result: r
        - done:
            return: ${r}

my_sub:
    params: [first, last: "Smith", country: "US"]
    steps:
        - build:
            return: ${"Hello " + first + " " + last + " from " + country}
```

---

## 2. Assign Step Tests

### 2.1 Basic Assign (VALID)

```yaml
# test_assign_basic.yaml
# VALID
- init:
    assign:
      - x: 5
      - y: "hello"
      - z: true
      - w: null
      - list: [1, 2, 3]
      - map:
          key1: "value1"
          key2: "value2"
```

### 2.2 Assign with Expressions (VALID)

```yaml
# test_assign_expressions.yaml
# VALID
- calc:
    assign:
      - x: 5
      - y: ${x + 1}
      - z: ${x * y}
      - msg: ${"Result: " + string(z)}
```

### 2.3 Assign with Next (VALID)

```yaml
# test_assign_next.yaml
# VALID
- init:
    assign:
      - x: 1
    next: done
- skipped:
    assign:
      - x: 2
- done:
    return: ${x}
```

### 2.4 Assign Over 50 (INVALID)

```yaml
# test_assign_over_50.yaml
# INVALID - max 50 assignments per step
- too_many:
    assign:
      - v1: 1
      - v2: 2
      - v3: 3
      - v4: 4
      - v5: 5
      - v6: 6
      - v7: 7
      - v8: 8
      - v9: 9
      - v10: 10
      - v11: 11
      - v12: 12
      - v13: 13
      - v14: 14
      - v15: 15
      - v16: 16
      - v17: 17
      - v18: 18
      - v19: 19
      - v20: 20
      - v21: 21
      - v22: 22
      - v23: 23
      - v24: 24
      - v25: 25
      - v26: 26
      - v27: 27
      - v28: 28
      - v29: 29
      - v30: 30
      - v31: 31
      - v32: 32
      - v33: 33
      - v34: 34
      - v35: 35
      - v36: 36
      - v37: 37
      - v38: 38
      - v39: 39
      - v40: 40
      - v41: 41
      - v42: 42
      - v43: 43
      - v44: 44
      - v45: 45
      - v46: 46
      - v47: 47
      - v48: 48
      - v49: 49
      - v50: 50
      - v51: 51
```

### 2.5 Assign Empty List (INVALID)

```yaml
# test_assign_empty.yaml
# INVALID - assign must have at least 1 entry
- empty:
    assign: []
```

---

## 3. Call Step Tests

### 3.1 HTTP GET (VALID)

```yaml
# test_call_http_get.yaml
# VALID
- fetch:
    call: http.get
    args:
      url: https://example.com/api
    result: response
```

### 3.2 HTTP POST with Auth (VALID)

```yaml
# test_call_http_post_auth.yaml
# VALID
- post_data:
    call: http.post
    args:
      url: https://us-central1-myproject.cloudfunctions.net/myfunc
      auth:
        type: OIDC
      body:
        message: "Hello World"
    result: the_message
```

### 3.3 Call Without Args (VALID)

```yaml
# test_call_no_args.yaml
# VALID - args is optional
- get_time:
    call: sys.now
    result: current_time
```

### 3.4 Call Without Result (VALID)

```yaml
# test_call_no_result.yaml
# VALID - result is optional
- log_it:
    call: sys.log
    args:
      data: "hello"
```

### 3.5 Call Subworkflow (VALID)

```yaml
# test_call_subworkflow.yaml
# VALID
main:
    steps:
        - invoke:
            call: my_helper
            args:
                x: 42
            result: output
        - done:
            return: ${output}

my_helper:
    params: [x]
    steps:
        - compute:
            return: ${x * 2}
```

---

## 4. Switch Step Tests

### 4.1 Basic Switch (VALID)

```yaml
# test_switch_basic.yaml
# VALID
- init:
    assign:
      - x: 5
- check:
    switch:
      - condition: ${x < 10}
        next: small
      - condition: ${x >= 10}
        next: big
- small:
    return: "small"
- big:
    return: "big"
```

### 4.2 Switch with Fallthrough (VALID)

```yaml
# test_switch_fallthrough.yaml
# VALID
- check:
    switch:
      - condition: ${x < 0}
        return: "negative"
    next: positive
- positive:
    return: "non-negative"
```

### 4.3 Switch with Embedded Steps (VALID)

```yaml
# test_switch_embedded_steps.yaml
# VALID
- check:
    switch:
      - condition: ${x == 1}
        steps:
          - compute:
              assign:
                - result: ${x + 10}
          - done:
              return: ${result}
      - condition: true
        return: "default"
```

### 4.4 Switch with Assign + Next (VALID)

```yaml
# test_switch_assign_next.yaml
# VALID - assign and next can coexist in a condition
- check:
    switch:
      - condition: ${"key" in args}
        assign:
          - value: ${args.key}
        next: process
- process:
    return: ${value}
```

### 4.5 Switch with Raise (VALID)

```yaml
# test_switch_raise.yaml
# VALID
- check:
    switch:
      - condition: ${x < 0}
        raise: "x must be non-negative"
      - condition: true
        return: ${x}
```

### 4.6 Switch Over 50 Conditions (INVALID)

```yaml
# test_switch_over_50.yaml
# INVALID - programmatically generate 51 conditions
# (In actual test code, build this dict with 51 condition entries)
```

---

## 5. For Loop Tests

### 5.1 List Iteration (VALID)

```yaml
# test_for_list.yaml
# VALID
- init:
    assign:
      - total: 0
      - items: [1, 2, 3, 4, 5]
- loop:
    for:
      value: item
      in: ${items}
      steps:
        - add:
            assign:
              - total: ${total + item}
- done:
    return: ${total}
```

### 5.2 Range Iteration (VALID)

```yaml
# test_for_range.yaml
# VALID
- init:
    assign:
      - total: 0
- loop:
    for:
      value: i
      range: [1, 10]
      steps:
        - add:
            assign:
              - total: ${total + i}
- done:
    return: ${total}
```

### 5.3 With Index (VALID)

```yaml
# test_for_index.yaml
# VALID
- loop:
    for:
      value: item
      index: idx
      in: ["a", "b", "c"]
      steps:
        - log:
            call: sys.log
            args:
              text: ${"Item " + string(idx) + ": " + item}
```

### 5.4 Both In and Range (INVALID)

```yaml
# test_for_both_in_range.yaml
# INVALID - in and range are mutually exclusive
- loop:
    for:
      value: x
      in: [1, 2, 3]
      range: [1, 10]
      steps:
        - noop:
            assign:
              - y: ${x}
```

### 5.5 Neither In nor Range (INVALID)

```yaml
# test_for_neither.yaml
# INVALID - exactly one of in/range required
- loop:
    for:
      value: x
      steps:
        - noop:
            assign:
              - y: ${x}
```

### 5.6 Index with Range (INVALID)

```yaml
# test_for_index_with_range.yaml
# INVALID - index is only valid with 'in'
- loop:
    for:
      value: i
      index: idx
      range: [1, 10]
      steps:
        - noop:
            assign:
              - x: ${i}
```

### 5.7 Break and Continue (VALID)

```yaml
# test_for_break_continue.yaml
# VALID
- init:
    assign:
      - results: []
- loop:
    for:
      value: item
      in: [1, null, 3, "STOP", 5]
      steps:
        - skip_null:
            switch:
              - condition: ${item == null}
                next: continue
              - condition: ${item == "STOP"}
                next: break
        - collect:
            assign:
              - results: ${list.concat(results, [item])}
- done:
    return: ${results}
```

---

## 6. Parallel Step Tests

### 6.1 Parallel Branches (VALID)

```yaml
# test_parallel_branches.yaml
# VALID
- init:
    assign:
      - results: {}
- parallel_work:
    parallel:
      shared: [results]
      branches:
        - branch_a:
            steps:
              - get_a:
                  call: http.get
                  args:
                    url: https://example.com/a
                  result: a
              - save_a:
                  assign:
                    - results.a: ${a.body}
        - branch_b:
            steps:
              - get_b:
                  call: http.get
                  args:
                    url: https://example.com/b
                  result: b
              - save_b:
                  assign:
                    - results.b: ${b.body}
- done:
    return: ${results}
```

### 6.2 Parallel For (VALID)

```yaml
# test_parallel_for.yaml
# VALID
- init:
    assign:
      - total: 0
      - items: [1, 2, 3, 4, 5]
- process:
    parallel:
      shared: [total]
      for:
        value: item
        in: ${items}
        steps:
          - add:
              assign:
                - total: ${total + item}
- done:
    return: ${total}
```

### 6.3 Parallel with Exception Policy (VALID)

```yaml
# test_parallel_exception_policy.yaml
# VALID
- work:
    parallel:
      exception_policy: continueAll
      shared: [results]
      branches:
        - safe:
            steps:
              - ok:
                  assign:
                    - results: ["ok"]
        - risky:
            steps:
              - fail:
                  raise: "oops"
```

### 6.4 Parallel with Concurrency Limit (VALID)

```yaml
# test_parallel_concurrency.yaml
# VALID
- work:
    parallel:
      concurrency_limit: 3
      for:
        value: i
        range: [1, 20]
        steps:
          - process:
              call: http.get
              args:
                url: ${"https://example.com/item/" + string(i)}
```

### 6.5 Parallel Only 1 Branch (INVALID)

```yaml
# test_parallel_1_branch.yaml
# INVALID - minimum 2 branches required
- work:
    parallel:
      branches:
        - only_one:
            steps:
              - step:
                  assign:
                    - x: 1
```

### 6.6 Parallel 11 Branches (INVALID)

```yaml
# test_parallel_11_branches.yaml
# INVALID - maximum 10 branches
- work:
    parallel:
      branches:
        - b1:
            steps:
              - s: { assign: [{ x: 1 }] }
        - b2:
            steps:
              - s: { assign: [{ x: 2 }] }
        - b3:
            steps:
              - s: { assign: [{ x: 3 }] }
        - b4:
            steps:
              - s: { assign: [{ x: 4 }] }
        - b5:
            steps:
              - s: { assign: [{ x: 5 }] }
        - b6:
            steps:
              - s: { assign: [{ x: 6 }] }
        - b7:
            steps:
              - s: { assign: [{ x: 7 }] }
        - b8:
            steps:
              - s: { assign: [{ x: 8 }] }
        - b9:
            steps:
              - s: { assign: [{ x: 9 }] }
        - b10:
            steps:
              - s: { assign: [{ x: 10 }] }
        - b11:
            steps:
              - s: { assign: [{ x: 11 }] }
```

### 6.7 Parallel Both Branches and For (INVALID)

```yaml
# test_parallel_both.yaml
# INVALID - branches and for are mutually exclusive
- work:
    parallel:
      branches:
        - b1:
            steps:
              - s: { assign: [{ x: 1 }] }
        - b2:
            steps:
              - s: { assign: [{ x: 2 }] }
      for:
        value: i
        range: [1, 5]
        steps:
          - s: { assign: [{ y: 1 }] }
```

---

## 7. Try/Except/Retry Tests

### 7.1 Try/Except Single Call (VALID)

```yaml
# test_try_except_call.yaml
# VALID
- attempt:
    try:
      call: http.get
      args:
        url: https://example.com/might-fail
      result: response
    except:
      as: e
      steps:
        - log:
            call: sys.log
            args:
              data: ${e.message}
        - default:
            return: "failed"
```

### 7.2 Try/Except Steps Block (VALID)

```yaml
# test_try_except_steps.yaml
# VALID
- attempt:
    try:
      steps:
        - get_token:
            call: http.post
            args:
              url: https://auth.example.com/token
            result: token
        - use_token:
            call: http.get
            args:
              url: https://api.example.com/data
              headers:
                Authorization: ${"Bearer " + token.body.access_token}
            result: data
    except:
      as: e
      steps:
        - handle:
            return: ${e.message}
```

### 7.3 Try/Retry Predefined (VALID)

```yaml
# test_try_retry_predefined.yaml
# VALID
- reliable:
    try:
      call: http.get
      args:
        url: https://example.com/api
      result: response
    retry: ${http.default_retry}
```

### 7.4 Try/Retry Custom Config (VALID)

```yaml
# test_try_retry_custom.yaml
# VALID
- reliable:
    try:
      call: http.post
      args:
        url: https://example.com/api
        body:
          data: "important"
      result: response
    retry:
      predicate: ${http.default_retry_predicate}
      max_retries: 5
      backoff:
        initial_delay: 1
        max_delay: 60
        multiplier: 2
```

### 7.5 Try/Retry/Except Combined (VALID)

```yaml
# test_try_retry_except.yaml
# VALID
- robust:
    try:
      call: http.get
      args:
        url: https://example.com/api
      result: response
    retry:
      predicate: ${http.default_retry_predicate}
      max_retries: 3
      backoff:
        initial_delay: 1
        max_delay: 30
        multiplier: 2
    except:
      as: e
      steps:
        - fallback:
            return: "all retries failed"
```

---

## 8. Return and Raise Tests

### 8.1 Return Scalar (VALID)

```yaml
# test_return_scalar.yaml
# VALID
- done:
    return: 42
```

### 8.2 Return Map (VALID)

```yaml
# test_return_map.yaml
# VALID
- done:
    return:
      status: "ok"
      count: 5
```

### 8.3 Return Expression (VALID)

```yaml
# test_return_expression.yaml
# VALID
- init:
    assign:
      - x: 10
- done:
    return: ${x * 2}
```

### 8.4 Raise String (VALID)

```yaml
# test_raise_string.yaml
# VALID
- fail:
    raise: "Something went wrong"
```

### 8.5 Raise Map (VALID)

```yaml
# test_raise_map.yaml
# VALID
- fail:
    raise:
      code: 404
      message: "Resource not found"
```

---

## 9. Nested Steps Tests

### 9.1 Basic Nested Steps (VALID)

```yaml
# test_nested_steps.yaml
# VALID
- group_a:
    steps:
      - step1:
          assign:
            - x: 1
      - step2:
          assign:
            - y: ${x + 1}
- group_b:
    steps:
      - step3:
          return: ${y}
```

### 9.2 Nested Steps with Next (VALID)

```yaml
# test_nested_steps_next.yaml
# VALID
- group:
    steps:
      - init:
          assign:
            - x: 42
    next: done
- skipped:
    assign:
      - x: 0
- done:
    return: ${x}
```

---

## 10. Complex Integration Tests

### 10.1 Full Workflow with All Step Types (VALID)

```yaml
# test_full_workflow.yaml
# VALID
main:
    params: [args]
    steps:
        - init:
            assign:
              - total: 0
              - items: ${args.items}
        - validate:
            switch:
              - condition: ${len(items) == 0}
                return: "empty"
        - process:
            for:
              value: item
              in: ${items}
              steps:
                - fetch:
                    try:
                      call: http.get
                      args:
                        url: ${"https://api.example.com/items/" + string(item)}
                      result: response
                    retry: ${http.default_retry}
                    except:
                      as: e
                      steps:
                        - log_err:
                            call: sys.log
                            args:
                              data: ${e}
                              severity: "WARNING"
                        - skip:
                            next: continue
                - accumulate:
                    assign:
                      - total: ${total + response.body.value}
        - done:
            return:
              total: ${total}
              count: ${len(items)}
```

### 10.2 Parallel with Nested Try/Except (VALID)

```yaml
# test_parallel_with_try.yaml
# VALID
- init:
    assign:
      - results: []
- parallel_fetch:
    parallel:
      shared: [results]
      branches:
        - api_a:
            steps:
              - fetch_a:
                  try:
                    call: http.get
                    args:
                      url: https://api-a.example.com/data
                    result: a_data
                  retry: ${http.default_retry}
                  except:
                    as: e
                    steps:
                      - default_a:
                          assign:
                            - a_data:
                                body: "fallback_a"
              - save_a:
                  assign:
                    - results: ${list.concat(results, [a_data.body])}
        - api_b:
            steps:
              - fetch_b:
                  try:
                    call: http.get
                    args:
                      url: https://api-b.example.com/data
                    result: b_data
                  except:
                    as: e
                    steps:
                      - default_b:
                          assign:
                            - b_data:
                                body: "fallback_b"
              - save_b:
                  assign:
                    - results: ${list.concat(results, [b_data.body])}
- done:
    return: ${results}
```

---

## 11. Test Organization Guidance

### Directory Structure

```
tests/
  conftest.py           # Shared fixtures, YAML loading helpers
  test_top_level.py     # Form A/B parsing
  test_assign.py        # Assign step validation
  test_call.py          # Call step validation
  test_switch.py        # Switch step validation
  test_for.py           # For loop validation
  test_parallel.py      # Parallel step validation
  test_try.py           # Try/except/retry validation
  test_return_raise.py  # Return and raise steps
  test_nested.py        # Nested steps
  test_integration.py   # Full workflow integration tests
  fixtures/             # YAML files (optional, can inline in tests)
```

### Test Patterns

```python
import pytest
from pydantic import ValidationError
from cloud_workflows.models import parse_workflow

def test_valid_form_a():
    yaml_str = """
    - step1:
        assign:
          - x: 1
    - step2:
        return: ${x}
    """
    result = parse_workflow(yaml_str)
    assert result is not None

def test_invalid_assign_over_50():
    yaml_str = "..."  # 51 assignments
    with pytest.raises(ValidationError):
        parse_workflow(yaml_str)
```
