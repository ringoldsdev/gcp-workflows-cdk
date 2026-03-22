# cloud-workflows-generator

A Python CDK for Google Cloud Workflows. Define workflows with a class-based imperative API, validate them against the full GCP Workflows spec, and emit YAML files.

```bash
pip install -e .
```

## Quick Start

```python
from cloud_workflows import Steps, Assign, Call, Return, build, expr

s = Steps()
s.step("init", Assign(x=10, y=20))
s.step("log", Call("sys.log", args={"text": expr("x + y")}))
s.step("done", Return(expr("x + y")))

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
s.step("init", Assign(x=10, greeting=expr('"Hello, " + name')))

# dict for complex keys (dotted paths, bracket syntax)
s.step("init", Assign({"config.http.timeout": 30, 'map["key"]': "value"}))

# combine dict and kwargs
s.step("init", Assign({"a.b.c": 1}, x=10))

# with jump target
s.step("init", Assign(x=10, next="process"))
```

#### Dot-path unnesting

Dot-separated keys are automatically expanded into nested dicts:

```python
s.step("init", Assign({"config.http.timeout": 30, "config.http.retries": 3}))
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
s.step("fetch", Call("http.get", args={"url": "https://example.com"}, result="response"))
s.step("log", Call("sys.log", args={"text": expr("response.body")}, next="done"))
```

### Return / Raise

```python
s.step("done", Return(expr("response.body")))
s.step("fail", Raise({"code": 404, "message": "Not found"}))
```

### Switch

```python
from cloud_workflows import Switch, Condition

s.step("check", Switch([
    Condition(expr("x > 0"), next="positive"),
    Condition(expr("x == 0"), returns="zero"),
    Condition(True, next="negative"),  # default case
]))
```

### For Loop

```python
from cloud_workflows import For

# With Steps container
inner = Steps()
inner.step("log", Call("sys.log", args={"text": expr("item")}))

s.step("loop", For(value="item", items=["a", "b", "c"], steps=inner))

# With callable (lambda receives a fresh Steps)
s.step("loop", For(
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.step("log", Call("sys.log", args={"text": expr("item")})),
))
```

### Parallel

```python
from cloud_workflows import Parallel

b1 = Steps()
b1.step("get_users", Call("http.get", args={"url": "https://example.com/users"}, result="users"))

b2 = Steps()
b2.step("get_orders", Call("http.get", args={"url": "https://example.com/orders"}, result="orders"))

s.step("work", Parallel(
    branches={"fetch_users": b1, "fetch_orders": b2},
    shared=["users", "orders"],
    concurrency_limit=2,
))

# Branches can also be callables:
s.step("work", Parallel(branches={
    "b1": lambda s: s.step("do", Call("sys.log", args={"text": "b1"})),
    "b2": lambda s: s.step("do", Call("sys.log", args={"text": "b2"})),
}))
```

### Try / Except / Retry

```python
from cloud_workflows import Try, Retry, Backoff

body = Steps()
body.step("fetch", Call("http.get", args={"url": "https://example.com"}, result="resp"))

except_steps = Steps()
except_steps.step("log", Call("sys.log", args={"text": expr("e.message")}))
except_steps.step("rethrow", Raise(expr("e")))

s.step("safe_call", Try(
    steps=body,
    retry=Retry(
        expr("http.default_retry_predicate"),
        max_retries=3,
        backoff=Backoff(initial_delay=1, max_delay=60, multiplier=2),
    ),
    error_steps=except_steps,
))

# Retry without backoff:
s.step("simple_retry", Try(
    steps=body,
    retry=Retry("http.default_retry", max_retries=5),
))

# Steps and error_steps also accept callables:
s.step("safe_call", Try(
    steps=lambda s: s.step("fetch", Call("http.get", args={"url": "https://example.com"}, result="resp")),
    error_steps=lambda s: s.step("handle", Raise(expr("e"))),
))
```

### Nested Steps

```python
from cloud_workflows import NestedSteps

inner = Steps()
inner.step("step_a", Call("sys.log", args={"text": "a"}))
inner.step("step_b", Call("sys.log", args={"text": "b"}))

s.step("group", NestedSteps(steps=inner, next="done"))
```

## Composition

### Method Chaining

`.step()` and `.merge()` return `self` for fluent chaining:

```python
s = Steps()
s.step("init", Assign(x=10)) \
 .step("log", Call("sys.log", args={"text": expr("x")})) \
 .step("done", Return(expr("x")))
```

### Merging Steps

Use `.merge()` to append steps from another container:

```python
def logging_steps(message):
    s = Steps()
    s.step("log", Call("sys.log", args={"text": message}))
    return s

def error_handler():
    body = Steps()
    body.step("op", Call("http.get", args={"url": "https://example.com"}, result="r"))
    except_steps = Steps()
    except_steps.step("fail", Raise(expr("e")))
    s = Steps()
    s.step("safe", Try(steps=body, error_steps=except_steps))
    return s

main = Steps()
main.step("init", Assign(status="starting"))
main.merge(logging_steps("Workflow started"))
main.merge(error_handler())
main.step("done", Return(expr("r.body")))
```

### Callables for Inline Steps

Compound steps (For, Parallel, Try, Switch, NestedSteps) accept callables wherever they take a `Steps` parameter. The callable receives a fresh `Steps` instance:

```python
s.step("loop", For(
    value="item",
    items=["a", "b", "c"],
    steps=lambda s: s.step("log", Call("sys.log", args={"text": expr("item")})),
))
```

### Factory Functions

```python
from cloud_workflows import Steps, Assign, Call, Return, build, expr

def api_workflow(url):
    s = Steps()
    s.step("init", Assign(endpoint=url))
    s.step("fetch", Call("http.get", args={"url": expr("endpoint")}, result="response"))
    s.step("done", Return(expr("response.body")))
    return s

build({
    "users.yaml": {"main": api_workflow("https://example.com/users")},
    "orders.yaml": {"main": api_workflow("https://example.com/orders")},
}, output_dir="output/")
```

## Subworkflows

For workflows with multiple subworkflows or runtime parameters, use `Steps(params=[...])` and pass a dict to `build()`:

```python
from cloud_workflows import Steps, Assign, Call, Return, build, expr

main = Steps()
main.step("greet", Call("make_greeting", args={"person": "Alice"}, result="msg"))
main.step("done", Return(expr("msg")))

helper = Steps(params=["person"])
helper.step("build", Assign(greeting=expr('"Hello, " + person')))
helper.step("done", Return(expr("greeting")))

build({"workflow.yaml": {"main": main, "helper": helper}})
```

`build()` always requires a `dict[str, Steps]` with a `"main"` key for each file entry:

```python
# Single simple workflow:
s = Steps()
s.step("init", Assign(x=10))
s.step("done", Return(expr("x")))
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

For the builder pipeline and validation pipeline architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).
