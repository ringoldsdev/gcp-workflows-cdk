# cloud-workflows-validator

A Pydantic v2 YAML validator and builder for Google Cloud Workflows syntax. Parses GCP Workflows YAML into strongly-typed Python models, performs three layers of validation (structural, expression syntax, variable resolution), and supports programmatic workflow construction with serialization back to YAML.

## Requirements

- Python >= 3.14
- pydantic >= 2.0
- pyyaml >= 6.0

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from cloud_workflows import analyze_yaml

yaml_str = """
- init:
    assign:
      - name: "Alice"
      - greeting: '${"Hello, " + name}'
- done:
    return: ${greeting}
"""

result = analyze_yaml(yaml_str)

print(result.is_valid)       # True
print(result.errors)         # []
print(result.warnings)       # []
print(type(result.workflow))  # <class 'cloud_workflows.models.SimpleWorkflow'>
```

## Programmatic Construction

Build workflows in Python and serialize to YAML. Uses the same Pydantic model classes as the parser — no separate builder layer.

```python
from cloud_workflows import (
    SimpleWorkflow, Step, AssignStep, CallStep, ReturnStep,
    expr, to_yaml, analyze_workflow,
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

# Serialize to YAML
print(to_yaml(workflow))

# Validate (structural + expression + variable analysis)
result = analyze_workflow(workflow)
print(result.is_valid)  # True
```

Output YAML:

```yaml
- init:
    assign:
      - name: Alice
      - greeting: '${"Hello, " + name}'
- log:
    call: sys.log
    args:
      text: ${greeting}
- done:
    return: ${greeting}
```

### Subworkflows

```python
from cloud_workflows import (
    SubworkflowsWorkflow, WorkflowDefinition, Step,
    AssignStep, CallStep, ReturnStep,
)

workflow = SubworkflowsWorkflow(workflows={
    "main": WorkflowDefinition(steps=[
        Step(name="call_helper", body=CallStep(
            call="greet", args={"person": "Alice"}, result="msg",
        )),
        Step(name="done", body=ReturnStep(return_="${msg}")),
    ]),
    "greet": WorkflowDefinition(
        params=["person"],
        steps=[
            Step(name="build", body=AssignStep(assign=[
                {"greeting": '${"Hello, " + person}'},
            ])),
            Step(name="reply", body=ReturnStep(return_="${greeting}")),
        ],
    ),
})
```

### Key points

- **Aliases handle Python reserved words**: use `return_`, `raise_`, `for_`, `in_`, `as_`, `except_`, `try_` as field names. Serialization emits the correct YAML keys automatically.
- **`expr()` helper**: wraps a string in `${...}` syntax — `expr("x + 1")` produces `"${x + 1}"`.
- **`to_yaml(workflow)`**: serializes any `SimpleWorkflow` or `SubworkflowsWorkflow` to a YAML string.
- **`analyze_workflow(workflow)`**: runs the full 3-stage validation pipeline on a programmatically-constructed workflow (no YAML round-trip needed).
- **Round-trip fidelity**: `parse_workflow(to_yaml(workflow))` produces an equivalent model.

---

## Public API

### Parsing only (structural validation)

| Function | Description |
|---|---|
| `parse_workflow(yaml_str)` | Parse YAML string into a `Workflow` model |
| `validate_yaml(yaml_str)` | Alias for `parse_workflow` |
| `validate_file(path)` | Parse a YAML file into a `Workflow` model |

### Serialization (programmatic → YAML)

| Function | Description |
|---|---|
| `to_yaml(workflow)` | Serialize a `SimpleWorkflow` or `SubworkflowsWorkflow` to YAML |
| `expr(body)` | Wrap string in `${...}` syntax |
| `workflow.to_dict()` | Serialize to Python dict/list (on `SimpleWorkflow`/`SubworkflowsWorkflow`) |
| `workflow.to_yaml()` | Serialize to YAML string (on `SimpleWorkflow`/`SubworkflowsWorkflow`) |

### Full analysis pipeline

| Function | Description |
|---|---|
| `analyze_yaml(yaml_str)` | Parse + validate expressions + analyze variables |
| `analyze_file(path)` | Same as `analyze_yaml` but reads from a file |
| `analyze_workflow(workflow)` | Same as `analyze_yaml` but takes a model (no YAML round-trip) |

Both return an `AnalysisResult` with:

- `.workflow` -- the parsed Pydantic model
- `.expression_errors` -- list of `ExpressionError` for invalid `${...}` syntax
- `.variable_issues` -- list of `VariableIssue` (errors and warnings)
- `.is_valid` -- `True` if no expression errors and no variable errors
- `.errors` -- combined list of all errors
- `.warnings` -- list of variable warnings (e.g., conditionally defined variables)

### Expression validation (standalone)

| Function | Description |
|---|---|
| `validate_expression(expr_body)` | Validate a single expression string (without `${}`). Returns `None` if valid, `ExpressionError` if not |
| `validate_all_expressions(value)` | Recursively find and validate all `${...}` in a value tree |
| `extract_expression_strings(value)` | Extract expression bodies from a value tree |
| `extract_variable_references(expr)` | Extract root variable names referenced in an expression |

### Variable analysis (standalone)

| Function | Description |
|---|---|
| `analyze_variables(workflow)` | Analyze a parsed `Workflow` model for variable reference issues. Returns list of `VariableIssue` |

---

## Architecture

The validator is organized into four modules, each responsible for one concern:

```
src/cloud_workflows/
    __init__.py       Public API re-exports
    models.py         Pydantic v2 models for structural validation
    expressions.py    Lexer + recursive-descent parser for ${...} expressions
    variables.py      Scope-based variable tracking and reference checking
    parser.py         Convenience functions and the full analysis pipeline
```

### Processing Pipeline

When you call `analyze_yaml(yaml_str)`, three stages run in sequence:

```
                  YAML string
                      |
                      v
    +-----------------------------------+
    |  Stage 1: Structural Validation   |
    |  (models.py -- Pydantic v2)       |
    |                                   |
    |  - yaml.safe_load() parses YAML   |
    |  - Pydantic models validate       |
    |    structure, field types,         |
    |    constraints (max 50 assigns,   |
    |    mutual exclusivity, etc.)      |
    |  - Output: Workflow model tree    |
    +-----------------------------------+
                      |
                      v
    +-----------------------------------+
    |  Stage 2: Expression Validation   |
    |  (expressions.py)                 |
    |                                   |
    |  - Walks raw YAML value tree      |
    |  - Finds all ${...} strings       |
    |  - Tokenizes each expression      |
    |  - Parses with recursive-descent  |
    |    parser to check syntax         |
    |  - Output: list[ExpressionError]  |
    +-----------------------------------+
                      |
                      v
    +-----------------------------------+
    |  Stage 3: Variable Analysis       |
    |  (variables.py)                   |
    |                                   |
    |  - Walks the Pydantic model tree  |
    |  - Builds scope/symbol table      |
    |  - For each expression, extracts  |
    |    variable references and checks |
    |    they resolve in current scope  |
    |  - Output: list[VariableIssue]    |
    +-----------------------------------+
                      |
                      v
                AnalysisResult
```

Stage 2 operates on the **raw YAML** (the plain Python dicts/lists from `yaml.safe_load`) because it needs to see the literal `${...}` strings before Pydantic stores them as opaque `Any` values. Stage 3 operates on the **Pydantic model tree** because it needs typed access to step structures (knowing which step is an `AssignStep` vs a `CallStep`, accessing `.result` fields, etc.).

---

## How the Lexer Works

The lexer (`expressions.py: tokenize()`) converts a raw expression string into a flat list of `Token` objects. Each token has a `type` (from the `TokenType` enum), a `value` (the matched text), and a `pos` (character offset in the source).

### Token Categories

| Category | Token Types | Examples |
|---|---|---|
| Literals | `INTEGER`, `DOUBLE`, `STRING` | `42`, `3.14`, `"hello"` |
| Keywords | `TRUE`, `FALSE`, `NULL`, `AND`, `OR`, `IN`, `NOT` | `true`, `and`, `not` |
| Identifiers | `IDENT` | `my_var`, `response`, `len` |
| Operators | `PLUS`, `MINUS`, `STAR`, `SLASH`, `PERCENT`, `EQ`, `NEQ`, `LT`, `LTE`, `GT`, `GTE` | `+`, `==`, `<=` |
| Delimiters | `LPAREN`, `RPAREN`, `LBRACKET`, `RBRACKET`, `LBRACE`, `RBRACE`, `DOT`, `COMMA`, `COLON` | `(`, `]`, `.` |
| End | `EOF` | (always appended) |

### Lexing Algorithm

The lexer is a single-pass linear scan. At each position it tries these rules in order:

1. **Skip whitespace** -- match `\s+` and advance.
2. **Two-character operators** -- look ahead one char to match `==`, `!=`, `<=`, `>=`. This must be checked before single-character operators so that `<=` is not tokenized as `<` then `=`.
3. **Single-character operators and delimiters** -- direct table lookup for `+`, `-`, `*`, `(`, `[`, `.`, etc.
4. **String literals** -- if the current char is `"` or `'`, delegate to `_lex_string()` which scans forward until the matching closing quote, handling backslash escapes (`\"`, `\\`, `\n`, `\t`). Raises `LexError` on unterminated strings.
5. **Numbers** -- regex match `\d+\.\d*` or `\.\d+` or `\d+`. If the match contains a `.`, the token is `DOUBLE`; otherwise `INTEGER`.
6. **Identifiers and keywords** -- regex match `[A-Za-z_][A-Za-z_0-9]*`. The matched word is looked up in the `KEYWORDS` dict; if found, it becomes a keyword token (`AND`, `OR`, etc.); otherwise it becomes `IDENT`.
7. If none of the above match, raise `LexError`.

An `EOF` token is always appended at the end.

### Example

Input: `len(items) > 0 and "key" in my_map`

```
Token(IDENT,   "len",    pos=0)
Token(LPAREN,  "(",      pos=3)
Token(IDENT,   "items",  pos=4)
Token(RPAREN,  ")",      pos=9)
Token(GT,      ">",      pos=11)
Token(INTEGER, "0",      pos=13)
Token(AND,     "and",    pos=15)
Token(STRING,  "key",    pos=19)
Token(IN,      "in",     pos=25)
Token(IDENT,   "my_map", pos=28)
Token(EOF,     "",       pos=34)
```

---

## How the Parser Works

The parser (`expressions.py: ExpressionParser`) is a **recursive-descent parser** that validates the token stream against the GCP Cloud Workflows expression grammar. It does not build an AST -- it only checks that the expression is syntactically valid. If any rule fails to match, it raises `ParseError` with the position and a description of what was expected.

### Grammar

The grammar is defined by the precedence hierarchy. Each level calls the next-tighter level, and operators at the current level are consumed in a loop. Lower rows bind tighter:

```
Precedence    Rule             Operators / Constructs
----------    ----             ----------------------
1 (lowest)    or_expr          or
2             and_expr         and
3             membership       in
4             comparison       ==  !=  <  <=  >  >=
5             addition         +  -
6             multiplication   *  /  %
7             unary            - (prefix)
8             primary_postfix  .field  [index]  (args)
9 (highest)   primary          literals, identifiers, (expr), [list], {map}
```

### Parsing Rules in Detail

**`parse()`** -- entry point. Calls `expression()`, then asserts the next token is `EOF`. If there are leftover tokens, the expression has trailing junk.

**`expression()`** -- delegates to `or_expr()`.

**`or_expr()`** -- parses `and_expr ("or" and_expr)*`. Calls `and_expr()` first, then loops while the next token is `OR`, consuming the operator and parsing another `and_expr`.

**`and_expr()`** -- same pattern: `membership ("and" membership)*`.

**`membership()`** -- parses `comparison ("in" comparison)?`. The `in` operator is not left-recursive -- at most one `in` per level.

**`comparison()`** -- parses `addition (COMP_OP addition)?`. Again, at most one comparison operator per level (no chaining like `a < b < c`).

**`addition()`** -- parses `multiplication (("+" | "-") multiplication)*`. Left-associative loop.

**`multiplication()`** -- parses `unary (("*" | "/" | "%") unary)*`. Left-associative loop.

**`unary()`** -- parses `"-" unary | primary_postfix`. The recursive call handles chained negation like `--x`.

**`primary_postfix()`** -- parses a `primary` followed by zero or more postfix accessors in a loop:
  - `.IDENT` -- dot member access (`response.body`)
  - `[expression]` -- bracket access (`items[0]`, `config["key"]`)
  - `(arguments?)` -- function call (`len(items)`, `string(42)`)

This is how `response.body.data[0].name` is parsed: `primary("response")` then `.body` then `.data` then `[0]` then `.name`.

**`primary()`** -- the base case. Matches one of:
  - Numeric literal (`INTEGER` or `DOUBLE`)
  - String literal (`STRING`)
  - Boolean/null (`TRUE`, `FALSE`, `NULL`)
  - Identifier (`IDENT`) -- variable name or function name (the call `()` is handled in postfix)
  - `NOT` keyword -- treated as an identifier-like primary (the call parens are handled in postfix, so `not(x)` parses as primary `not` + postfix `(x)`)
  - Parenthesized expression -- `(` expression `)`
  - List literal -- `[` list_items? `]`
  - Map literal -- `{` map_items? `}`

**`list_items()`** -- parses `expression ("," expression)* ","?`. Trailing commas are allowed.

**`map_items()`** -- parses `map_entry ("," map_entry)* ","?`. Each `map_entry` is `expression ":" expression`.

**`arguments()`** -- same shape as `list_items`: `expression ("," expression)* ","?`.

### How `not()` Works

GCP Workflows uses function syntax for logical NOT: `not(x)` instead of `!x` or `not x`. In the parser, `not` is a keyword that is accepted in `primary()` as a primary value (like an identifier). The postfix loop then matches the `(x)` as a function call. This means `not(a and b)` parses as: primary `not`, then postfix call `(a and b)`.

### Error Reporting

When a rule encounters an unexpected token, it raises `ParseError` with:
- The expected token type (e.g., "Expected RPAREN")
- The actual token found (e.g., "got EOF")
- The character position in the source

The top-level `validate_expression()` function catches both `LexError` and `ParseError` and returns an `ExpressionError` dataclass.

### Walk-through: `(x + 5) * 2 > 20 and len(items) != 0`

```
parse()
  expression()
    or_expr()
      and_expr()
        membership()
          comparison()               -- will find ">"
            addition()
              multiplication()       -- will find "*"
                unary()
                  primary_postfix()
                    primary()        -- sees "(", enters parenthesized expr
                      expression()   -- parses "x + 5"
                      expect RPAREN
                [loop] sees "*"
                unary()
                  primary_postfix()
                    primary()        -- literal 2
            sees ">"
            addition()
              multiplication()
                unary()
                  primary_postfix()
                    primary()        -- literal 20
        [and_expr loop] sees "and"
        membership()
          comparison()               -- will find "!="
            addition()
              multiplication()
                unary()
                  primary_postfix()
                    primary()        -- IDENT "len"
                    [postfix loop] sees "("
                      arguments()    -- parses "items"
                    expect RPAREN
            sees "!="
            addition()
              multiplication()
                unary()
                  primary_postfix()
                    primary()        -- literal 0
  expect EOF -- done
```

---

## How `${...}` Extraction Works

Before the parser can run, expression bodies must be extracted from YAML string values. The function `_extract_expressions()` handles this with a brace-depth-counting scan:

1. Scan forward until `${` is found.
2. Set depth = 1, advance past `${`.
3. For each character:
   - If `"` or `'`, skip the entire quoted string (handling `\` escapes).
   - If `{`, increment depth.
   - If `}`, decrement depth. If depth reaches 0, the expression ends.
4. Extract the substring between `${` and the matching `}`.

This correctly handles nested braces in map literals like `${ {"a": 1} }` and strings containing braces like `${"hello {world}"}`.

The public function `extract_expression_strings(value)` recursively walks any Python value (str, list, dict) and collects all expression bodies.

---

## How Variable Analysis Works

The variable analyzer (`variables.py: VariableAnalyzer`) walks the Pydantic model tree and maintains a `Scope` chain to track which variables are defined at each point.

### The Scope Chain

`Scope` is a linked list of symbol tables. Each scope has:
- `_vars` -- a dict mapping variable names to `VariableDefinition` records
- `parent` -- pointer to the enclosing scope (or `None` for the root)
- `lookup(name)` -- checks `_vars`, then recurses to `parent`

```
Workflow scope (params: name, age)
    |
    +-- For loop scope (value: item, index: idx)
    |       Variables defined in loop body are added HERE,
    |       but the loop vars are NOT visible outside.
    |
    +-- Try/except scope
            |
            +-- Except scope (as: e)
                    The 'e' variable is only visible in this scope.
```

### Variable Definition Sources

| Source | Kind | Scope | Example |
|---|---|---|---|
| `params` | `PARAM` | Workflow root | `params: [name, age]` |
| `assign` step | `ASSIGN` | Current scope | `assign: [{x: 10}]` |
| `result` on `call` | `RESULT` | Current scope | `result: response` |
| `result` on `try` call | `RESULT` | Current scope | `try: {call: ..., result: r}` |
| `for` value | `FOR_VALUE` | Child (loop) scope | `for: {value: item}` |
| `for` index | `FOR_INDEX` | Child (loop) scope | `for: {index: idx}` |
| `except as` | `EXCEPT_AS` | Child (except) scope | `except: {as: e}` |

### Walk Order

The analyzer walks steps **in order**, top to bottom, just like the runtime would execute them. At each step:

1. Check all expression references in the step's values (RHS of assigns, call args, conditions, return/raise values).
2. Define any new variables introduced by the step (LHS of assigns, result fields).

This means a variable referenced before its assign step is flagged as an error.

### Nested Steps Share Scope

Nested `steps:` blocks do **not** create a new scope. Variables defined inside nested steps are visible outside, and vice versa. This matches the GCP runtime behavior.

### Switch Branch Analysis

When a switch step is encountered, the analyzer processes each branch independently and collects the set of variables each branch defines. Then:

- Variables defined in **all** branches get `Certainty.DEFINITE`.
- Variables defined in **some** branches get `Certainty.MAYBE`.

When a later step references a `MAYBE` variable, a **warning** is emitted (not an error) because the variable might not exist depending on which branch ran.

### Parallel Branch Analysis

Each parallel branch gets its own child scope. Variables defined inside branches are branch-local and not visible outside the parallel step. The `shared` list declares which pre-existing variables branches are allowed to write to, but the analyzer currently does not enforce write restrictions on shared variables.

### Subworkflow Name Exclusion

In a Form B workflow (with named subworkflows), the analyzer collects all subworkflow names before analysis begins. When checking variable references, any identifier that matches a subworkflow name is skipped (it's a valid call target, not a variable).

### Root Variable Extraction

When an assign LHS has nested access like `config.key1` or `items[0]`, the helper `_root_var_name()` extracts just the root (`config`, `items`). Only the root is registered in the scope. This means `config.key1: "new_value"` is treated as a modification of the existing `config` variable, not a new variable named `config.key1`.

For expression references, `extract_variable_references()` similarly returns only root identifiers. `response.body.data[0].name` yields `["response"]`. Identifiers preceded by a `.` are member access and are excluded. Built-in function names (`len`, `keys`, `int`, `double`, `string`, `bool`, `type`, `not`) followed by `(` are excluded.

---

## Project Structure

```
cloud-workflows-validator/
    pyproject.toml
    README.md
    .opencode/
        skills/
            pydantic-v2/
                SKILL.md        Pydantic v2 patterns reference (OpenCode agent skill)
    docs/
        01_overview.md          GCP Workflows top-level structure
        02_steps.md             Step type schemas
        03_error_handling.md    Try/except/retry/raise
        04_control_flow.md      Switch, for, parallel, jumps
        05_data_model.md        Variables, expressions, data types, functions
        06_pydantic_design.md   Pydantic model design spec
        07_test_fixtures.md     YAML test examples and conventions
    src/cloud_workflows/
        __init__.py             Public API
        models.py               Pydantic v2 models + serialization (607 lines)
        expressions.py          Lexer + parser (604 lines)
        variables.py            Variable analyzer (492 lines)
        parser.py               Pipeline functions + analyze_workflow (108 lines)
    tests/
        conftest.py             Shared helpers (parse, load_fixture, parse_fixture)
        test_assign.py          Assign step tests
        test_call.py            Call step tests
        test_cdk.py             Programmatic construction + serialization tests (71 tests)
        test_expressions.py     Expression lexer/parser tests (120 tests)
        test_for.py             For loop tests
        test_integration.py     Full workflow integration tests
        test_nested.py          Nested steps tests
        test_parallel.py        Parallel step tests
        test_return_raise.py    Return/raise tests
        test_switch.py          Switch step tests
        test_top_level.py       Form A/B top-level tests
        test_try.py             Try/except/retry tests
        test_variables.py       Variable tracking tests (29 tests)
        fixtures/
            assign/             Assign step YAML fixtures
            call/               Call step YAML fixtures
            cdk/                Programmatic construction YAML fixtures (7 files)
            expressions/        Expression validation YAML fixtures
            for/                For loop YAML fixtures
            integration/        Full workflow YAML fixtures
            nested/             Nested steps YAML fixtures
            parallel/           Parallel step YAML fixtures
            return_raise/       Return/raise YAML fixtures
            switch/             Switch step YAML fixtures
            top_level/          Form A/B YAML fixtures
            try/                Try/except YAML fixtures
            variables/          Variable tracking YAML fixtures
```

## Running Tests

```bash
python -m pytest tests/ -v
```

272 tests total: 52 structural, 120 expression, 29 variable tracking, 71 programmatic construction/serialization.
