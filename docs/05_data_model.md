# GCP Cloud Workflows Syntax Reference: Data Model

> Variables, expressions, data types, and built-in functions.
>
> Source: https://cloud.google.com/workflows/docs/reference/syntax/variables,
> https://cloud.google.com/workflows/docs/reference/syntax/expressions,
> https://cloud.google.com/workflows/docs/reference/syntax/datatypes

---

## 1. Variables

### Declaration and Assignment

Variables are created implicitly through `assign` steps. There is no explicit declaration
syntax:

```yaml
- init:
    assign:
      - name: "Alice"        # string
      - age: 30              # integer
      - score: 95.5          # double
      - active: true         # boolean
      - data: null           # null
      - items: [1, 2, 3]    # list
      - config:              # map
          key1: "value1"
          key2: "value2"
```

### Scope

- Variables have **workflow-level scope** within a subworkflow (or main).
- Once assigned, a variable is visible to all subsequent steps in the same subworkflow.
- Variables inside `steps` blocks (nested steps) are **not** block-scoped -- they have
  the same workflow-level scope.
- **Exception**: `for` loop variables (`value`, `index`) have **loop-local scope** and are
  cleared after the loop exits.
- **Exception**: Parallel branch variables are branch-local. Only `shared` variables can
  be written to from branches.

### Accessing Nested Values

```yaml
# Dot notation for maps
${config.key1}

# Bracket notation for maps
${config["key1"]}

# List indexing (0-based)
${items[0]}

# Chained access
${response.body.data[0].name}
```

### Modifying Nested Values

```yaml
- update:
    assign:
      - config.key1: "new_value"
      - config["key2"]: "new_value2"
      - items[0]: "updated"
```

### Clearing Variables

Set to `null` to clear (free memory for large variables):

```yaml
- clear:
    assign:
      - bigData: null
```

---

## 2. Expressions

### Expression Syntax

All expressions are wrapped in `${...}`:

```yaml
# In assign values
- calc:
    assign:
      - result: ${x + y * 2}

# In condition fields
- check:
    switch:
      - condition: ${x > 10}
        next: big

# In string interpolation (within expressions)
- msg:
    assign:
      - greeting: ${"Hello, " + name + "!"}

# In call args
- request:
    call: http.get
    args:
      url: ${"https://api.example.com/users/" + string(userId)}
```

### Expression Context

Expressions can appear in:
- `assign` step values (right-hand side)
- `condition` fields in switch
- `call` step `args` values
- `return` step values
- `raise` step values
- `for` step `in` and `range` values
- `next` field values (usually just step names, not expressions)
- `parallel` `concurrency_limit` value

### Literal Values in Expressions

```yaml
${42}           # integer
${3.14}         # double
${"hello"}      # string
${true}         # boolean
${false}        # boolean
${null}         # null
${[1, 2, 3]}   # list literal
${{"a": 1}}    # map literal (note: double braces)
```

---

## 3. Data Types

### Primitive Types

| Type | Examples | Notes |
|------|----------|-------|
| `integer` | `42`, `-7`, `0` | 64-bit signed integer |
| `double` | `3.14`, `-0.5`, `1.0` | 64-bit IEEE 754 |
| `string` | `"hello"`, `'world'` | UTF-8 encoded |
| `boolean` | `true`, `false` | |
| `null` | `null` | |
| `bytes` | (from base64 decode) | Binary data |

### Composite Types

| Type | Syntax | Notes |
|------|--------|-------|
| `list` | `[1, 2, 3]` | Ordered, 0-indexed, heterogeneous |
| `map` | `{"key": "value"}` | String keys, heterogeneous values |

### Type Coercion

- Integer and double can be mixed in arithmetic (result is double if either operand is
  double).
- String concatenation with `+` requires both operands to be strings. Use `string()` to
  convert: `${"count: " + string(count)}`.
- No implicit boolean coercion -- conditions must evaluate to actual boolean values.

---

## 4. Operators

### Arithmetic

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Addition / string concatenation | `${x + y}`, `${"a" + "b"}` |
| `-` | Subtraction | `${x - y}` |
| `*` | Multiplication | `${x * y}` |
| `/` | Division | `${x / y}` |
| `%` | Modulo | `${x % y}` |
| `-` (unary) | Negation | `${-x}` |

### Comparison

| Operator | Description |
|----------|-------------|
| `==` | Equal |
| `!=` | Not equal |
| `<` | Less than |
| `<=` | Less or equal |
| `>` | Greater than |
| `>=` | Greater or equal |

### Logical

| Operator | Description |
|----------|-------------|
| `and` | Logical AND |
| `or` | Logical OR |
| `not()` | Logical NOT (function syntax) |

### Membership

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Check membership | `${"key" in my_map}`, `${item in my_list}` |

---

## 5. Built-in Functions

### Type Conversion

| Function | Description | Example |
|----------|-------------|---------|
| `int()` | Convert to integer | `${int("42")}` |
| `double()` | Convert to double | `${double("3.14")}` |
| `string()` | Convert to string | `${string(42)}` |
| `bool()` | Convert to boolean | `${bool(1)}` |

### Type Checking

| Function | Description | Example |
|----------|-------------|---------|
| `type()` | Returns type name as string | `${type(x)}` -> `"string"`, `"int"`, `"double"`, `"bool"`, `"list"`, `"map"`, `"null"` |

### Map Functions

| Function | Description | Example |
|----------|-------------|---------|
| `keys()` | Get list of map keys | `${keys(my_map)}` |
| `len()` | Get length (list or map) | `${len(my_list)}` |
| `map.get()` | Get value with default | Call: `map.get` with args `{map: m, key: k, default: d}` |
| `map.delete()` | Delete a key | Call: `map.delete` |
| `map.merge()` | Merge two maps | Call: `map.merge` |
| `map.merge_nested()` | Deep merge | Call: `map.merge_nested` |

### List Functions

| Function | Description |
|----------|-------------|
| `len()` | Get length |
| `list.concat()` | Concatenate lists |
| `list.prepend()` | Prepend element |

### String Functions

| Function | Description |
|----------|-------------|
| `text.decode()` | Decode bytes to string |
| `text.encode()` | Encode string to bytes |
| `text.find_all()` | Find all occurrences |
| `text.find_all_regex()` | Find all regex matches |
| `text.match_regex()` | Test regex match |
| `text.replace_all()` | Replace all occurrences |
| `text.replace_all_regex()` | Replace all regex matches |
| `text.split()` | Split string |
| `text.substring()` | Extract substring |
| `text.to_lower()` | Convert to lowercase |
| `text.to_upper()` | Convert to uppercase |
| `text.url_decode()` | URL decode |
| `text.url_encode()` | URL encode |
| `text.url_encode_plus()` | URL encode (plus spaces) |

### Math Functions

| Function | Description |
|----------|-------------|
| `math.abs()` | Absolute value |
| `math.floor()` | Floor |
| `math.max()` | Maximum |
| `math.min()` | Minimum |

### JSON Functions

| Function | Description |
|----------|-------------|
| `json.decode()` | Parse JSON string to value |
| `json.encode()` | Encode value to bytes (JSON) |
| `json.encode_to_string()` | Encode value to JSON string |

### System Functions

| Function | Description |
|----------|-------------|
| `sys.get_env()` | Get environment variable |
| `sys.log()` | Write to log |
| `sys.now()` | Current timestamp (Unix epoch seconds as double) |
| `sys.sleep()` | Sleep for N seconds |
| `sys.sleep_until()` | Sleep until timestamp |

### Base64 Functions

| Function | Description |
|----------|-------------|
| `base64.decode()` | Decode base64 string to bytes |
| `base64.encode()` | Encode bytes to base64 string |

### Hash Functions

| Function | Description |
|----------|-------------|
| `hash.compute_checksum()` | Compute checksum |
| `hash.compute_hmac()` | Compute HMAC |

### Time Functions

| Function | Description |
|----------|-------------|
| `time.format()` | Format timestamp |
| `time.parse()` | Parse timestamp string |

### UUID Functions

| Function | Description |
|----------|-------------|
| `uuid.generate()` | Generate random UUID |

### Retry Functions

| Function | Description |
|----------|-------------|
| `retry.always()` | Always retry predicate |
| `retry.default_backoff()` | Default backoff config |
| `retry.never()` | Never retry predicate |

---

## 6. Standard Library Call Patterns

Most standard library functions are called via `call` steps, not inline in expressions:

```yaml
# Expression-context functions (used inside ${...})
${len(my_list)}
${keys(my_map)}
${int("42")}
${string(42)}
${type(x)}
${"key" in my_map}

# Call-context functions (used via call step)
- step:
    call: sys.log
    args:
      data: "hello"
      severity: "INFO"

- step:
    call: json.decode
    args:
      data: '{"key": "value"}'
    result: parsed
```

### Expression-Context vs Call-Context

**Expression-context** (inline in `${...}`):
- `len()`, `keys()`, `int()`, `double()`, `string()`, `bool()`, `type()`, `not()`

**Call-context** (via `call` step):
- `http.*`, `sys.*`, `json.*`, `text.*`, `math.*`, `base64.*`, `hash.*`, `time.*`,
  `uuid.*`, `list.*`, `map.*`, `retry.*`, `events.*`

---

## 7. Notes for Validator Implementation

### What to Validate

The validator should:
- Accept any value type in `assign` right-hand side, `return`, `raise`, `args` values
- Accept expressions (`${...}` strings) anywhere a value is expected
- Not attempt to parse or evaluate expression contents (that's a runtime concern)
- Treat `${...}` strings as opaque `str` values at validation time

### What NOT to Validate

The validator should NOT:
- Type-check expression results
- Verify function names in `call` steps exist in the standard library
- Verify variable references resolve to declared variables
- Parse the expression language inside `${...}`
- Enforce any runtime limits (memory, execution time, etc.)

### Type Representation in Pydantic

Since YAML values can be any type, use `Any` for value positions:
- `assign` entry values: `Any`
- `return` value: `Any`
- `raise` value: `Any`
- `args` dict values: `Any`
- `condition` value: `Any` (typically a string expression, but could be `true`/`false`)
