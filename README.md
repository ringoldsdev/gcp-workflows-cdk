# cloud-workflows-generator

A Python CDK for Google Cloud Workflows. Define workflows with a callback-based builder API, validate them against the full GCP Workflows spec, and emit YAML files.

```bash
pip install -e .
```

## Quick Start

```python
from cloud_workflows import Workflow, build, expr

build({
    "workflow.yaml": Workflow()
        .assign("init", x=10, y=20)
        .call("log", func="sys.log", args={"text": expr("x + y")})
        .returns("done", value=expr("x + y")),
})
```

Output (`workflow.yaml`):

```yaml
- init:
    assign:
      - x: 10
      - y: 20
- log:
    call: sys.log
    args:
      text: ${x + y}
- done:
    return: ${x + y}
```

## Core Patterns

Every step type supports two forms: **keyword arguments** for simple cases and a **callback** for full control. The callback receives a sub-builder and returns it via chaining.

### Assign

```python
# kwargs — each key-value pair becomes an assignment
s.assign("init", x=10, greeting=expr('"Hello, " + name'))

# callback — .set() for individual items, .next() for jump target
s.assign("init", lambda a: a
    .set("config", {"retries": 3, "timeout": 30})
    .set("items", [1, 2, 3])
    .next("process")
)
```

#### Dot-path unnesting

Dot-separated keys in `.set()` (and kwargs) are automatically unnested into nested dicts:

```python
# These are equivalent:
s.assign("init", lambda a: a.set("config.http.timeout", 30).set("config.http.retries", 3))
s.assign("init", **{"config.http.timeout": 30, "config.http.retries": 3})
```

Both produce:

```yaml
- init:
    assign:
      - config:
          http:
            timeout: 30
      - config:
          http:
            retries: 3
```

### Call

```python
# kwargs
s.call("fetch", func="http.get", args={"url": "https://example.com"}, result="response")

# callback
s.call("fetch", lambda c: c
    .func("http.get")
    .args(url="https://example.com", headers={"Accept": "application/json"})
    .result("response")
    .next("process")
)
```

### Return / Raise

```python
s.returns("done", value=expr("response.body"))
s.raises("fail", value={"code": 404, "message": "Not found"})

# callback
s.returns("done", lambda r: r.value(expr("x + y")))
s.raises("fail", lambda r: r.value(expr("e")))
```

### Switch

```python
# callback — each .condition() adds a branch
s.switch("check", lambda sw: sw
    .condition(expr("x > 0"), next="positive")
    .condition(expr("x == 0"), returns="zero")
    .condition(True, next="negative")  # default case
)
```

### For Loop

```python
# kwargs — value is always required, provide either in_ or range_
s.loop("loop", value="item", in_=expr("items"), steps=inner_steps)
s.loop("count", value="i", range_=[1, 10], steps=inner_steps)

# callback
s.loop("loop", lambda f: f
    .value("item")
    .index("idx")
    .items(["a", "b", "c"])
    .steps(lambda s: s
        .call("log", func="sys.log", args={"text": expr("item")})
    ),
)
```

### Parallel

```python
# callback — .branch() takes a name and a StepBuilder (or lambda)
s.parallel("work", lambda p: p
    .branch("fetch_users", lambda s: s
        .call("get", func="http.get", args={"url": "https://example.com/users"}, result="users")
    )
    .branch("fetch_orders", lambda s: s
        .call("get", func="http.get", args={"url": "https://example.com/orders"}, result="orders")
    )
    .shared(["users", "orders"])
    .concurrency_limit(2)
)
```

### Try / Except / Retry

```python
# callback — .body() wraps the operation, .retry() and .exception() add error handling
s.do_try("safe_call", lambda t: t
    .body(lambda s: s
        .call("fetch", func="http.get", args={"url": "https://example.com"}, result="resp")
    )
    .retry(
        predicate=expr("http.default_retry_predicate"),
        max_retries=3,
        backoff={"initial_delay": 1, "max_delay": 60, "multiplier": 2},
    )
    .exception(error="e", steps=lambda s: s
        .call("log", func="sys.log", args={"text": expr("e.message")})
        .raises("rethrow", value=expr("e"))
    )
)
```

### Nested Steps

```python
s.nested_steps("group", lambda ns: ns
    .body(lambda s: s
        .call("step_a", func="sys.log", args={"text": "a"})
        .call("step_b", func="sys.log", args={"text": "b"})
    )
    .next("done")
)
```

## Composition

### `.apply()` — Merge Steps

`.apply()` copies steps from another builder into the current one. Use it to compose reusable fragments.

```python
def logging_middleware(message):
    return StepBuilder().call("log", func="sys.log", args={"text": message})

def error_handler():
    return StepBuilder().do_try("safe", lambda t: t
        .body(lambda s: s.call("op", func="http.get", args={"url": "https://example.com"}, result="r"))
        .exception(error="e", steps=lambda s: s.raises("fail", value=expr("e")))
    )

workflow = (
    Workflow()
    .assign("init", status="starting")
    .apply(logging_middleware("Workflow started"))
    .apply(error_handler())
    .returns("done", value=expr("r.body"))
)()
```

### Sub-builder `.apply()` — Merge Into Step Internals

Each sub-builder also supports `.apply()` for composing within a single step:

```python
common_headers = Assign().set("content_type", "application/json").set("accept", "application/json")

s.assign("init", lambda a: a
    .set("url", "https://example.com")
    .apply(common_headers)
)
```

### Factory Functions

```python
from cloud_workflows import StepBuilder, Workflow, build, expr

def api_workflow(name, url):
    return (
        StepBuilder()
        .assign("init", endpoint=url)
        .call("fetch", func="http.get", args={"url": expr("endpoint")}, result="response")
        .returns("done", value=expr("response.body"))
    )

build({
    "users.yaml": Workflow().apply(api_workflow("users", "https://example.com/users")),
    "orders.yaml": Workflow().apply(api_workflow("orders", "https://example.com/orders")),
}, output_dir="output/")
```

## Subworkflows

When a workflow needs helper functions or accepts runtime parameters, use `Subworkflow` with a dict:

```python
from cloud_workflows import Workflow, Subworkflow, build, expr

main = Subworkflow().call("greet", func="make_greeting", args={"person": "Alice"}, result="msg").returns("done", value=expr("msg"))
helper = Subworkflow(params=["person"]).assign("build", greeting=expr('"Hello, " + person')).returns("done", value=expr("greeting"))

workflow = Workflow({"main": main, "helper": helper})()
```

For simple workflows (no subworkflows, no params), chain steps directly on `Workflow`:

```python
workflow = Workflow().assign("init", x=10).returns("done", value=expr("x"))()
```

Calling the `Workflow` instance (or `.build()`) returns a `SimpleWorkflow` (flat list) when there is a single "main" with no params, otherwise a `SubworkflowsWorkflow` (dict of named workflows). The standalone `build()` function auto-finalizes unfinalized `Workflow` objects, so you can pass them directly.

## Validation

Every workflow can be validated against the full GCP Workflows spec: structural rules, expression syntax, and variable resolution.

```python
from cloud_workflows import analyze_workflow, analyze_yaml

# Validate a builder-constructed workflow
result = analyze_workflow(workflow)
print(result.is_valid)          # True / False
print(result.errors)            # list of errors (expression + variable)
print(result.warnings)          # list of warnings (e.g. conditionally-defined variables)

# Validate raw YAML
result = analyze_yaml(open("workflow.yaml").read())
print(result.is_valid)
print(result.expression_errors) # list of ExpressionError
print(result.variable_issues)   # list of VariableIssue
```

The analysis pipeline runs three stages:

1. **Structural** — Pydantic v2 models enforce types, field constraints (max 50 assigns, mutual exclusivity of `in`/`range`, branch counts, etc.)
2. **Expression** — A Pratt parser validates every `${...}` expression for correct syntax
3. **Variable** — Scope-based analysis checks that every referenced variable is defined before use

## Advanced: Using Pydantic Models Directly

The builder API is syntactic sugar over Pydantic model classes. For maximum control, construct models directly:

```python
from cloud_workflows import (
    SimpleWorkflow, SubworkflowsWorkflow, WorkflowDefinition,
    Step, AssignStep, CallStep, ReturnStep, RaiseStep,
    SwitchStep, SwitchCondition,
    ForStep, ForBody,
    ParallelStep, ParallelBody, Branch,
    TryStep, TryCallBody, TryStepsBody, ExceptBody,
    RetryConfig, BackoffConfig,
    NestedStepsStep,
    expr, to_yaml, parse_workflow,
)

workflow = SimpleWorkflow(steps=[
    Step(name="init", body=AssignStep(assign=[
        {"name": "Alice"},
        {"greeting": expr('"Hello, " + name')},
    ])),
    Step(name="log", body=CallStep(
        call="sys.log",
        args={"text": expr("greeting")},
    )),
    Step(name="done", body=ReturnStep(return_=expr("greeting"))),
])

yaml_str = to_yaml(workflow)           # serialize to YAML string
roundtrip = parse_workflow(yaml_str)   # parse back to model
```

### Aliases for Python Reserved Words

Pydantic field names use trailing underscores for Python reserved words. Serialization emits the correct YAML keys automatically:

| Python field | YAML key |
|---|---|
| `return_` | `return` |
| `raise_` | `raise` |
| `for_` | `for` |
| `in_` | `in` |
| `as_` | `as` |
| `except_` | `except` |
| `try_` | `try` |

> **Note:** The builder API provides friendlier names so you don't need trailing underscores in most code. See the table below. The original underscore names continue to work.
>
> | Preferred method | Original | Sub-builder class | Original |
> |---|---|---|---|
> | `.returns(name, ...)` | `.return_()`, `.do_return()` | `Returns` | `Return_`, `DoReturn` |
> | `.raises(name, ...)` | `.raise_()`, `.do_raise()` | `Raises` | `Raise_`, `DoRaise` |
> | `.loop(name, ...)` | `.for_()` | `Loop` | `For` |
> | `.do_try(name, ...)` | `.try_()` | `DoTry` | `Try_` |

### Model Construction Examples

```python
# Switch with embedded actions
SwitchStep(switch=[
    SwitchCondition(condition=expr("x > 0"), next="positive"),
    SwitchCondition(condition=expr("x == 0"), return_="zero"),
    SwitchCondition(condition=True, next="negative"),
])

# For loop
ForStep(for_=ForBody(
    value="item", in_=["a", "b", "c"],
    steps=[Step(name="log", body=CallStep(call="sys.log", args={"text": expr("item")}))],
))

# Parallel branches
ParallelStep(parallel=ParallelBody(branches=[
    Branch(name="b1", steps=[Step(name="s", body=CallStep(call="sys.log", args={"text": "b1"}))]),
    Branch(name="b2", steps=[Step(name="s", body=CallStep(call="sys.log", args={"text": "b2"}))]),
]))

# Try/except/retry
TryStep(
    try_=TryCallBody(call="http.get", args={"url": "https://example.com"}, result="resp"),
    retry=RetryConfig(
        predicate=expr("http.default_retry_predicate"),
        max_retries=3,
        backoff=BackoffConfig(initial_delay=1, max_delay=60, multiplier=2),
    ),
    except_=ExceptBody(as_="e", steps=[
        Step(name="handle", body=RaiseStep(raise_=expr("e"))),
    ]),
)
```

## Reference

Full API documentation, expression parser internals, and variable analysis behavior are in [REFERENCE.md](./REFERENCE.md).

For the builder pipeline, StepBase dict-state architecture, and how Pydantic validation fits into the build process, see [ARCHITECTURE.md](./ARCHITECTURE.md).
