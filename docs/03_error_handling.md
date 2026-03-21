# GCP Cloud Workflows Syntax Reference: Error Handling

> Comprehensive reference for try/except/retry/raise constructs.
>
> Source: https://cloud.google.com/workflows/docs/reference/syntax/catching-errors,
> https://cloud.google.com/workflows/docs/reference/syntax/retrying,
> https://cloud.google.com/workflows/docs/reference/syntax/raising-errors,
> https://cloud.google.com/workflows/docs/reference/syntax/error-types

---

## 1. Try Step (Full Detail)

The `try` step wraps operations that might fail, with optional `retry` and `except` blocks.

### Schema

```yaml
- STEP_NAME:
    try:
      # Form A: Single call
      call: FUNCTION_NAME
      args:
        ARG_1: VALUE_1
      result: OUTPUT_VAR
      # Form B: Multi-step
      steps:
        - STEP_A:
            ...
        - STEP_B:
            ...
    retry: RETRY_POLICY       # optional
    except:                   # optional
      as: ERROR_VAR
      steps:
        - HANDLER_STEP:
            ...
```

### TryBody (Dual-Form)

The value of `try` is polymorphic -- it can be **either** of:

**Form A: Single Call** -- The try body contains `call`, optionally `args` and `result`,
just like a regular call step:

```yaml
try:
  call: http.get
  args:
    url: https://example.com
  result: response
```

Fields for Form A:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `call` | `str` | **Yes** | Function name |
| `args` | `Dict[str, Any]` | No | Arguments |
| `result` | `str` | No | Output variable |

**Form B: Steps Block** -- The try body contains a `steps` list:

```yaml
try:
  steps:
    - step_a:
        assign:
          - x: 1
    - step_b:
        call: http.get
        args:
          url: https://example.com
        result: response
```

Fields for Form B:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `steps` | `List[Step]` | **Yes** | Ordered steps (recursive) |

### Discrimination Rule

- If the `try` value (dict) has a `call` key -> Form A (single call)
- If the `try` value (dict) has a `steps` key -> Form B (steps block)
- Exactly one of `call` or `steps` must be present in the try body.

---

## 2. Except Block

The `except` block catches errors raised by the `try` block (after retries are exhausted,
if `retry` is present).

### Schema

```yaml
except:
  as: ERROR_VAR_NAME    # required
  steps:                # required
    - HANDLER_STEP:
        ...
```

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `as` | `str` | **Yes** | Variable name to bind the error map to |
| `steps` | `List[Step]` | **Yes** | Steps to execute when an error is caught |

### Error Map Structure

When an error is caught, the variable named in `as` receives an **error map** with these
fields:

| Field | Type | Always Present | Notes |
|-------|------|----------------|-------|
| `tags` | `List[str]` | **Yes** | List of error tag strings (e.g. `["HttpError"]`) |
| `message` | `str` | **Yes** | Human-readable error message |
| `code` | `int` | For HTTP errors | HTTP status code (e.g. 404, 500) |
| `headers` | `Dict[str, str]` | For HTTP errors | Response headers |
| `body` | `Any` | For HTTP errors | Response body |

### Accessing Error Fields

```yaml
except:
  as: e
  steps:
    - log_error:
        call: sys.log
        args:
          data: ${"Error tag: " + e.tags[0] + ", message: " + e.message}
    - check_code:
        switch:
          - condition: ${e.code == 404}
            return: "Not found"
          - condition: ${e.code == 500}
            raise: ${e}  # re-raise
```

---

## 3. Retry Policy

The `retry` field defines automatic retry behavior for the `try` block. It is
**polymorphic** -- it can be a string expression (predefined policy) or a config object.

### Form A: Predefined Retry Policy (String Expression)

```yaml
retry: ${http.default_retry}
```

This is a string expression that evaluates to a complete retry policy (predicate + backoff).

**Predefined retry policies:**

| Expression | Description |
|------------|-------------|
| `${http.default_retry}` | Retries on HTTP 5xx and connection errors. For idempotent operations. |
| `${http.default_retry_non_idempotent}` | Same but only for non-idempotent-safe errors (429, 503). |

### Form B: Custom Retry Config Object

```yaml
retry:
  predicate: ${http.default_retry_predicate}
  max_retries: 5
  backoff:
    initial_delay: 1
    max_delay: 60
    multiplier: 2
```

### RetryConfig Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `predicate` | `str (expression)` | **Yes** | Expression evaluating to a retry predicate (subworkflow name or predefined predicate) |
| `max_retries` | `int` | **Yes** | Maximum number of retries (must be positive) |
| `backoff` | `BackoffConfig` | **Yes** | Backoff timing configuration |

### BackoffConfig Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `initial_delay` | `number` | **Yes** | Initial delay in seconds before first retry |
| `max_delay` | `number` | **Yes** | Maximum delay in seconds between retries |
| `multiplier` | `number` | **Yes** | Multiplier for exponential backoff |

### Predefined Retry Predicates

Predicates determine **which errors** should trigger a retry:

| Expression | Description |
|------------|-------------|
| `${http.default_retry_predicate}` | Retries on HTTP 5xx, 429, and connection errors |
| `${http.default_retry_predicate_non_idempotent}` | Retries on 429, 503, and connection errors only |

### Custom Retry Predicate (Subworkflow)

You can define a subworkflow as a custom predicate. It receives one parameter (the error
map) and must return `true` to retry or `false` to stop:

```yaml
main:
    steps:
        - try_step:
            try:
              call: http.get
              args:
                url: https://example.com
              result: response
            retry:
              predicate: ${my_retry_predicate}
              max_retries: 3
              backoff:
                initial_delay: 2
                max_delay: 60
                multiplier: 4

my_retry_predicate:
    params: [e]
    steps:
        - check:
            switch:
              - condition: ${e.code == 429}
                return: true
              - condition: ${e.code >= 500}
                return: true
        - otherwise:
            return: false
```

### Retry Discrimination Rule

- If `retry` value is a **string** (or expression like `${...}`) -> Form A (predefined policy)
- If `retry` value is a **dict** with keys `predicate`, `max_retries`, `backoff` -> Form B (custom config)

---

## 4. Raise Step (Full Detail)

Raises a custom error. Can be caught by a surrounding `try/except`.

### Schema

```yaml
# String literal
- STEP_NAME:
    raise: "Error message"

# Expression (e.g. re-raise a caught error)
- STEP_NAME:
    raise: ${e}

# Map (structured error)
- STEP_NAME:
    raise:
      code: 404
      message: "Resource not found"
```

### Value Type

The `raise` value is `Any` -- it can be:
- A string literal
- An expression (`${...}`)
- A map/dict with arbitrary keys (commonly `code` and `message`)
- A number, boolean, list, or null (though maps and strings are most common)

### Behavior

- If caught by a `try/except`, the raised value is bound to the `as` variable.
- If not caught, it terminates the workflow with a FAILED state.
- When re-raising a caught error (`raise: ${e}`), the original error is propagated.

---

## 5. Error Types (Tags)

Every workflow error has a `tags` field (list of strings). These are all the error tags
that the Workflows runtime can produce:

| Tag | Description |
|-----|-------------|
| `AuthError` | Authentication/authorization failure |
| `ConnectionError` | Generic connection failure |
| `ConnectionFailedError` | Failed to establish connection |
| `HttpError` | HTTP call returned non-2xx status code |
| `IndexError` | List index out of bounds |
| `KeyError` | Map key does not exist |
| `OperationError` | Long-running operation failed |
| `ParallelNestingError` | Exceeded maximum parallel nesting depth |
| `RecursionError` | Exceeded maximum call stack depth |
| `ResourceLimitError` | Exceeded a resource limit (memory, etc.) |
| `ResponseTypeError` | Unexpected response type from a call |
| `SystemError` | Internal system error |
| `TimeoutError` | Operation timed out |
| `TypeError` | Type mismatch in expression |
| `UnhandledBranchError` | A parallel branch raised an unhandled error |
| `ValueError` | Invalid value in expression |
| `ZeroDivisionError` | Division by zero |

### HttpError Structure

When an HTTP call returns a non-2xx status code, the error map has additional fields:

```yaml
# Error map for HTTP errors:
{
  "tags": ["HttpError"],
  "message": "HTTP request failed with status code 404",
  "code": 404,
  "headers": {"content-type": "application/json", ...},
  "body": {"error": {"message": "Not found", ...}}
}
```

### Checking Error Tags

Use the `in` operator to check if an error has a specific tag:

```yaml
except:
  as: e
  steps:
    - check:
        switch:
          - condition: ${"HttpError" in e.tags}
            next: handle_http
          - condition: ${"TimeoutError" in e.tags}
            next: handle_timeout
```

---

## 6. Complete Examples

### Try/Except with Error Inspection

```yaml
- make_request:
    try:
      call: http.get
      args:
        url: https://example.com/api
      result: api_response
    except:
      as: e
      steps:
        - known_errors:
            switch:
              - condition: ${not("HttpError" in e.tags)}
                raise: ${e}  # re-raise non-HTTP errors
        - handle_404:
            switch:
              - condition: ${e.code == 404}
                return: "Not found"
              - condition: ${e.code == 403}
                return: "Forbidden"
        - unhandled:
            raise: ${e}
```

### Try/Retry with Predefined Policy

```yaml
- reliable_request:
    try:
      call: http.get
      args:
        url: https://example.com/api
      result: api_response
    retry: ${http.default_retry}
```

### Try/Retry with Custom Config

```yaml
- custom_retry:
    try:
      call: http.post
      args:
        url: https://example.com/api
        body:
          data: "important"
      result: api_response
    retry:
      predicate: ${http.default_retry_predicate}
      max_retries: 10
      backoff:
        initial_delay: 0.5
        max_delay: 120
        multiplier: 2.5
```

### Try/Retry/Except Combined

```yaml
- robust_call:
    try:
      call: http.get
      args:
        url: https://example.com/api
      result: response
    retry:
      predicate: ${http.default_retry_predicate}
      max_retries: 5
      backoff:
        initial_delay: 1
        max_delay: 60
        multiplier: 2
    except:
      as: e
      steps:
        - log_failure:
            call: sys.log
            args:
              data: ${e}
              severity: "ERROR"
        - return_default:
            return: "default_value"
```

### Try with Steps Block (Multi-Step)

```yaml
- complex_try:
    try:
      steps:
        - get_token:
            call: http.post
            args:
              url: https://auth.example.com/token
              body:
                grant_type: "client_credentials"
            result: token_response
        - use_token:
            call: http.get
            args:
              url: https://api.example.com/data
              headers:
                Authorization: ${"Bearer " + token_response.body.access_token}
            result: data_response
    retry: ${http.default_retry}
    except:
      as: e
      steps:
        - handle:
            return: ${e.message}
```

---

## 7. Interaction Between Retry and Except

1. When **only `retry`** is present: retries on matching errors; if retries exhausted, the
   error propagates up (unhandled).
2. When **only `except`** is present: errors go directly to the except handler (no retries).
3. When **both `retry` and `except`** are present: retries first. If all retries are
   exhausted, the error is then passed to the except handler.
4. When **neither** is present: the try block is effectively a no-op wrapper; errors
   propagate up immediately.

---

## 8. Notes for Validator Implementation

- `try` body discrimination: check for `call` key (Form A) vs `steps` key (Form B)
- `retry` discrimination: check if value is string/expression (Form A) vs dict (Form B)
- `retry` config dict must have all three fields: `predicate`, `max_retries`, `backoff`
- `backoff` dict must have all three fields: `initial_delay`, `max_delay`, `multiplier`
- `except` block must have both `as` and `steps`
- Error tags are informational; the validator does not need to validate tag values at
  parse time (they are runtime values)
- The `retry` and `except` fields live at the **same level** as `try` (siblings, not
  nested inside `try`)
