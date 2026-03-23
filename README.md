# cloud-workflows-generator

A Python CDK for Google Cloud Workflows. Define workflows with a class-based imperative API, validate them against the full GCP Workflows spec, and emit YAML files.

```bash
pip install -e .
```

## Quick Start

```python
from cloud_workflows import Steps, Condition, build, expr

s = (Steps()
    .assign("init", x=10, y=20)
    .call("log", "sys.log", args={"text": expr("x + y")})
    .returns("done", expr("x + y")))

build({"workflow.yaml": {"main": s}})
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

## Step Types

### Assign

```python
# kwargs — each key-value pair becomes an assignment
s.assign("init", x=10, greeting=expr('"Hello, " + name'))

# dict for complex keys (dotted paths, bracket syntax)
s.assign("init", {"config.http.timeout": 30, 'map["key"]': "value"})

# combine dict and kwargs
s.assign("init", {"a.b.c": 1}, x=10)

# with jump target
s.assign("init", x=10, next="process")
```

#### Dot-path unnesting

Dot-separated keys are automatically expanded into nested dicts:

```python
s.assign("init", {"config.http.timeout": 30, "config.http.retries": 3})
```

Produces:

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
(s.call("fetch", "http.get",
        args={"url": "https://example.com"},
        result="response")
  .call("log", "sys.log",
        args={"text": expr("response.body")},
        next="done"))
```

### Return / Raise

```python
(s.returns("done", expr("response.body"))
  .raises("fail", {"code": 404, "message": "Not found"}))
```

### Switch

```python
from cloud_workflows import Condition

s.switch("check", [
    Condition(expr("x > 0"), next="positive"),
    Condition(expr("x == 0"), returns="zero"),
    Condition(True, next="negative"),  # default case
])
```

### For Loop

```python
# With Steps container
inner = Steps().call("log", "sys.log", args={"text": expr("item")})

s.loop("loop", value="item", items=["a", "b", "c"], steps=inner)

# With callable (lambda receives a fresh Steps)
s.loop("loop",
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.call("log", "sys.log", args={"text": expr("item")}),
)
```

### Parallel

```python
b1 = Steps().call("get_users", "http.get",
                   args={"url": "https://example.com/users"},
                   result="users")

b2 = Steps().call("get_orders", "http.get",
                   args={"url": "https://example.com/orders"},
                   result="orders")

s.parallel("work",
    branches={"fetch_users": b1, "fetch_orders": b2},
    shared=["users", "orders"],
    concurrency_limit=2,
)

# Branches can also be callables:
s.parallel("work", branches={
    "b1": lambda s: s.call("do", "sys.log", args={"text": "b1"}),
    "b2": lambda s: s.call("do", "sys.log", args={"text": "b2"}),
})
```

### Try / Except / Retry

```python
from cloud_workflows import Retry, Backoff

body = Steps().call("fetch", "http.get",
                    args={"url": "https://example.com"},
                    result="resp")

except_steps = (Steps()
    .call("log", "sys.log", args={"text": expr("e.message")})
    .raises("rethrow", expr("e")))

s.do_try("safe_call",
    steps=body,
    retry=Retry(
        expr("http.default_retry_predicate"),
        max_retries=3,
        backoff=Backoff(initial_delay=1, max_delay=60, multiplier=2),
    ),
    error_steps=except_steps,
)

# Retry without backoff:
s.do_try("simple_retry",
    steps=body,
    retry=Retry("http.default_retry", max_retries=5),
)

# Steps and error_steps also accept callables:
s.do_try("safe_call",
    steps=lambda s: s.call("fetch", "http.get",
                           args={"url": "https://example.com"},
                           result="resp"),
    error_steps=lambda s: s.raises("handle", expr("e")),
)
```

### Nested Steps

```python
inner = (Steps()
    .call("step_a", "sys.log", args={"text": "a"})
    .call("step_b", "sys.log", args={"text": "b"}))

s.nested("group", steps=inner, next="done")
```

## Expression Helpers

### expr()

Wraps an expression body in `${...}`:

```python
expr("x + 1")  # => "${x + 1}"
```

### concat()

Builds a `+` concatenation expression from a list of items. Each item is auto-converted:

- `expr("var")` expressions are unwrapped to their body
- Plain strings become quoted literals
- Numbers, booleans, and `None` become their GCP literal form

```python
from cloud_workflows import concat

concat(["Hello", expr("name")], " ")
# => '${"Hello" + " " + name}'

concat([expr("first"), expr("last")], " ")
# => '${first + " " + last}'

concat([expr("a"), expr("b"), expr("c")], ", ")
# => '${a + ", " + b + ", " + c}'

# Without separator — direct concatenation:
concat([expr("prefix"), expr("suffix")])
# => '${prefix + suffix}'
```

Use it anywhere an expression string is expected:

```python
s = (Steps()
    .assign("init", first="Jane", last="Doe")
    .assign("greet", greeting=concat(["Hello, ", expr("first"), " ", expr("last"), "!"]))
    .returns("done", expr("greeting")))
```

## Composition

### Method Chaining

All alias methods (and `.step()`, `.merge()`) return `self` for fluent chaining:

```python
s = (Steps()
    .assign("init", x=10)
    .call("log", "sys.log", args={"text": expr("x")})
    .returns("done", expr("x")))
```

### Merging Steps

Use `.merge()` to append steps from another container:

```python
def logging_steps(message):
    return Steps().call("log", "sys.log", args={"text": message})

def error_handler():
    body = Steps().call("op", "http.get",
                        args={"url": "https://example.com"},
                        result="r")
    except_steps = Steps().raises("fail", expr("e"))
    return Steps().do_try("safe", steps=body, error_steps=except_steps)

main = (Steps()
    .assign("init", status="starting")
    .merge(logging_steps("Workflow started"))
    .merge(error_handler())
    .returns("done", expr("r.body")))
```

### Callables for Inline Steps

Compound steps (`.loop()`, `.parallel()`, `.do_try()`, `.switch()`, `.nested()`) accept callables wherever they take a `steps` parameter. The callable receives a fresh `Steps` instance:

```python
s.loop("loop",
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.call("log", "sys.log", args={"text": expr("item")}),
)
```

### Factory Functions

```python
from cloud_workflows import Steps, build, expr

def api_workflow(url):
    return (Steps()
        .assign("init", endpoint=url)
        .call("fetch", "http.get",
              args={"url": expr("endpoint")},
              result="response")
        .returns("done", expr("response.body")))

build({
    "users.yaml": {"main": api_workflow("https://example.com/users")},
    "orders.yaml": {"main": api_workflow("https://example.com/orders")},
}, output_dir="output/")
```

### Generic .step() Method

For full control, the generic `.step()` method accepts any `StepType` instance directly:

```python
from cloud_workflows import Assign, Call, Return

s = (Steps()
    .step("init", Assign(x=10, y=20))
    .step("log", Call("sys.log", args={"text": expr("x")}))
    .step("done", Return(expr("x"))))
```

This is useful when you need to pass pre-built step objects or when working with custom step factories.

## Subworkflows

For workflows with multiple subworkflows or runtime parameters, use `Steps(params=[...])` and pass a dict to `build()`:

```python
from cloud_workflows import Steps, build, expr

main = (Steps()
    .call("greet", "make_greeting",
          args={"person": "Alice"},
          result="msg")
    .returns("done", expr("msg")))

helper = (Steps(params=["person"])
    .assign("build", greeting=expr('"Hello, " + person'))
    .returns("done", expr("greeting")))

build({"workflow.yaml": {"main": main, "helper": helper}})
```

`build()` always requires a `dict[str, Steps]` with a `"main"` key for each file entry:

```python
# Single simple workflow:
s = (Steps()
    .assign("init", x=10)
    .returns("done", expr("x")))
build({"workflow.yaml": {"main": s}})
```

A single `"main"` without params produces `SimpleWorkflow` (flat list). Multiple workflows or params produce `SubworkflowsWorkflow` (dict of named workflows).

## Validation

Every workflow can be validated against the full GCP Workflows spec: structural rules, expression syntax, and variable resolution.

```python
from cloud_workflows import analyze_workflow, analyze_yaml

# Validate a builder-constructed workflow
result = analyze_workflow(s._finalize())
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
    Step(name="done", body=ReturnStep(return_value=expr("greeting"))),
])

yaml_str = to_yaml(workflow)           # serialize to YAML string
roundtrip = parse_workflow(yaml_str)   # parse back to model
```

### Aliases for Python Reserved Words

Pydantic field names avoid Python reserved words by using descriptive suffixes. Serialization emits the correct YAML keys automatically via aliases:

| Python field | YAML key |
|---|---|
| `return_value` | `return` |
| `raise_value` | `raise` |
| `for_body` | `for` |
| `in_value` | `in` |
| `as_value` | `as` |
| `except_body` | `except` |
| `try_body` | `try` |

### Model Construction Examples

```python
# Switch with embedded actions
SwitchStep(switch=[
    SwitchCondition(condition=expr("x > 0"), next="positive"),
    SwitchCondition(condition=expr("x == 0"), return_value="zero"),
    SwitchCondition(condition=True, next="negative"),
])

# For loop
ForStep(for_body=ForBody(
    value="item", in_value=["a", "b", "c"],
    steps=[Step(name="log", body=CallStep(call="sys.log", args={"text": expr("item")}))],
))

# Parallel branches
ParallelStep(parallel=ParallelBody(branches=[
    Branch(name="b1", steps=[Step(name="s", body=CallStep(call="sys.log", args={"text": "b1"}))]),
    Branch(name="b2", steps=[Step(name="s", body=CallStep(call="sys.log", args={"text": "b2"}))]),
]))

# Try/except/retry
TryStep(
    try_body=TryCallBody(call="http.get", args={"url": "https://example.com"}, result="resp"),
    retry=RetryConfig(
        predicate=expr("http.default_retry_predicate"),
        max_retries=3,
        backoff=BackoffConfig(initial_delay=1, max_delay=60, multiplier=2),
    ),
    except_body=ExceptBody(as_value="e", steps=[
        Step(name="handle", body=RaiseStep(raise_value=expr("e"))),
    ]),
)
```

## Reference

Full API documentation, expression parser internals, and variable analysis behavior are in [REFERENCE.md](./REFERENCE.md).

For the builder pipeline and validation pipeline architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).
