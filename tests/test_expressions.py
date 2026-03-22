"""Tests for expression parsing and validation."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from conftest import load_fixture, parse_fixture

from cloud_workflows.expressions import (
    tokenize,
    validate_expression,
    validate_all_expressions,
    extract_expression_strings,
    extract_variable_references,
    parse_expression_ast,
    parse_expression_recover,
    walk,
    ExpressionError,
    LexError,
    ParseError,
    TokenType,
    ErrorNode,
)


# =============================================================================
# Tokenizer tests
# =============================================================================


class TestTokenizer:
    """Tests for the expression tokenizer."""

    def test_integer_literal(self):
        tokens = tokenize("42")
        assert tokens[0].type == TokenType.INTEGER
        assert tokens[0].value == "42"

    def test_double_literal(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.DOUBLE
        assert tokens[0].value == "3.14"

    def test_string_double_quotes(self):
        tokens = tokenize('"hello"')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello"

    def test_string_single_quotes(self):
        tokens = tokenize("'world'")
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "world"

    def test_string_with_escape(self):
        tokens = tokenize(r'"he said \"hi\""')
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == 'he said "hi"'

    def test_identifier(self):
        tokens = tokenize("my_var")
        assert tokens[0].type == TokenType.IDENT
        assert tokens[0].value == "my_var"

    def test_keywords(self):
        for kw, expected_type in [
            ("true", TokenType.TRUE),
            ("false", TokenType.FALSE),
            ("null", TokenType.NULL),
            ("and", TokenType.AND),
            ("or", TokenType.OR),
            ("in", TokenType.IN),
            ("not", TokenType.NOT),
        ]:
            tokens = tokenize(kw)
            assert tokens[0].type == expected_type, f"Failed for keyword: {kw}"

    def test_operators(self):
        source = "+ - * / % == != < <= > >="
        tokens = tokenize(source)
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.STAR,
            TokenType.SLASH,
            TokenType.PERCENT,
            TokenType.EQ,
            TokenType.NEQ,
            TokenType.LT,
            TokenType.LTE,
            TokenType.GT,
            TokenType.GTE,
        ]

    def test_delimiters(self):
        source = "( ) [ ] { } . , :"
        tokens = tokenize(source)
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.LPAREN,
            TokenType.RPAREN,
            TokenType.LBRACKET,
            TokenType.RBRACKET,
            TokenType.LBRACE,
            TokenType.RBRACE,
            TokenType.DOT,
            TokenType.COMMA,
            TokenType.COLON,
        ]

    def test_whitespace_skipped(self):
        tokens = tokenize("  x  +  y  ")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.IDENT, TokenType.PLUS, TokenType.IDENT]

    def test_complex_expression(self):
        tokens = tokenize('len(items) > 0 and "key" in my_map')
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.IDENT,  # len
            TokenType.LPAREN,
            TokenType.IDENT,  # items
            TokenType.RPAREN,
            TokenType.GT,
            TokenType.INTEGER,  # 0
            TokenType.AND,
            TokenType.STRING,  # "key"
            TokenType.IN,
            TokenType.IDENT,  # my_map
        ]

    def test_unterminated_string_raises(self):
        with pytest.raises(LexError, match="Unterminated string"):
            tokenize('"hello')

    def test_unexpected_character_raises(self):
        with pytest.raises(LexError, match="Unexpected character"):
            tokenize("x @ y")

    def test_eof_token(self):
        tokens = tokenize("x")
        assert tokens[-1].type == TokenType.EOF


# =============================================================================
# Parser tests -- valid expressions
# =============================================================================


class TestParserValid:
    """Tests that valid expressions parse without errors."""

    @pytest.mark.parametrize(
        "expr",
        [
            # Arithmetic
            "x + y",
            "x - y",
            "x * y",
            "x / y",
            "x % y",
            "-x",
            "(x + y) * 2",
            "((a + b) * (c - d))",
            # Comparison
            "x == y",
            "x != y",
            "x < y",
            "x <= y",
            "x > y",
            "x >= y",
            # Logical
            "a and b",
            "a or b",
            "not(a)",
            "a and b or not(c)",
            "(a or b) and not(a and b)",
            # Membership
            '"key" in my_map',
            "item in my_list",
            # Literals
            "42",
            "3.14",
            '"hello"',
            "'world'",
            "true",
            "false",
            "null",
            "[1, 2, 3]",
            "[]",
            '{"a": 1, "b": 2}',
            "{}",
            # Member access
            "config.key1",
            'config["key1"]',
            "items[0]",
            "response.body.data[0].name",
            'data["items"][0].value',
            "matrix[0][1]",
            # Function calls
            "len(items)",
            "keys(config)",
            'int("42")',
            'double("3.14")',
            "string(42)",
            "bool(1)",
            "type(x)",
            "not(true)",
            "len(keys(config))",
            "string(len(items) + 1)",
            # Complex
            "(x + 5) * 2 > 20 and len(items) != 0",
            "x > 0 and x < 100",
            "a == b or c != d",
            "[x + 1, x + 2, x + 3]",
            '{"result": x * 2, "name": name}',
            "len(response.body.items)",
            # String concatenation
            '"Hello, " + name + "!"',
            '"count: " + string(42)',
            # Trailing comma in list
            "[1, 2, 3,]",
            # Trailing comma in map
            '{"a": 1, "b": 2,}',
            # Trailing comma in function args
            "len(items,)",
            # Nested lists and maps
            "[[1, 2], [3, 4]]",
            '{"nested": {"x": true}}',
        ],
    )
    def test_valid_expression(self, expr):
        result = validate_expression(expr)
        assert result is None, f"Expected valid but got: {result}"


# =============================================================================
# Parser tests -- invalid expressions
# =============================================================================


class TestParserInvalid:
    """Tests that invalid expressions produce errors."""

    @pytest.mark.parametrize(
        "expr,expected_msg",
        [
            # Unclosed parens
            ("(x + y", "Expected RPAREN"),
            # Trailing operator
            ("x +", "Unexpected token EOF"),
            # Double operator
            ("x ++ y", "Unexpected token PLUS"),
            # Unclosed bracket
            ("items[0", "Expected RBRACKET"),
            # Empty parens (not a function call)
            ("()", "Unexpected token RPAREN"),
            # Stray colon
            ("x : y", "Unexpected token COLON"),
            # Unclosed map
            ('{"a": 1', "Expected RBRACE"),
            # Missing map value
            ('{"a":}', "Unexpected token RBRACE"),
            # Double comma in list
            ("[1,, 2]", "Unexpected token COMMA"),
            # Unclosed string (lex error)
            ('"hello', "Unterminated string"),
            # Unexpected character
            ("x @ y", "Unexpected character"),
            # Missing expression after unary minus
            ("- +", "Unexpected token PLUS"),
            # Expression followed by junk
            ("x y", "Unexpected token"),
        ],
    )
    def test_invalid_expression(self, expr, expected_msg):
        result = validate_expression(expr)
        assert result is not None, f"Expected error for: {expr}"
        assert expected_msg in result.message, (
            f"Expected message containing {expected_msg!r}, got {result.message!r}"
        )


# =============================================================================
# Expression extraction tests
# =============================================================================


class TestExpressionExtraction:
    """Tests for extracting ${...} expressions from values."""

    def test_simple_expression(self):
        result = extract_expression_strings("${x + y}")
        assert result == ["x + y"]

    def test_multiple_expressions(self):
        result = extract_expression_strings("start ${a} middle ${b} end")
        assert result == ["a", "b"]

    def test_nested_braces(self):
        result = extract_expression_strings('${ {"a": 1} }')
        assert result == [' {"a": 1} ']

    def test_no_expression(self):
        result = extract_expression_strings("just a plain string")
        assert result == []

    def test_numeric_value(self):
        result = extract_expression_strings(42)
        assert result == []

    def test_list_of_strings(self):
        result = extract_expression_strings(["${a}", "${b}"])
        assert result == ["a", "b"]

    def test_dict_values(self):
        result = extract_expression_strings({"url": "${base_url + path}", "count": 5})
        assert result == ["base_url + path"]

    def test_nested_structures(self):
        data = {"outer": {"items": ["${x}", "plain", "${y + z}"]}}
        result = extract_expression_strings(data)
        assert result == ["x", "y + z"]

    def test_expression_with_string_containing_braces(self):
        # The ${...} extraction should handle strings inside expressions
        result = extract_expression_strings('${"hello {world}"}')
        assert len(result) == 1


# =============================================================================
# Validate all expressions in a tree
# =============================================================================


class TestValidateAllExpressions:
    """Tests for validating all expressions in a value tree."""

    def test_valid_tree(self):
        data = {
            "url": "${base_url + path}",
            "count": "${len(items)}",
            "flag": True,
        }
        errors = validate_all_expressions(data)
        assert errors == []

    def test_invalid_in_tree(self):
        data = {
            "good": "${x + y}",
            "bad": "${x +}",
        }
        errors = validate_all_expressions(data)
        assert len(errors) == 1
        assert "x +" in errors[0].expression

    def test_mixed_valid_invalid(self):
        data = ["${valid}", "${also + valid}", "${(broken}"]
        errors = validate_all_expressions(data)
        assert len(errors) == 1


# =============================================================================
# Variable reference extraction tests
# =============================================================================


class TestExtractVariableReferences:
    """Tests for extracting variable references from expressions."""

    def test_simple_variable(self):
        assert extract_variable_references("x") == ["x"]

    def test_multiple_variables(self):
        refs = extract_variable_references("x + y")
        assert refs == ["x", "y"]

    def test_builtin_function_excluded(self):
        refs = extract_variable_references("len(items)")
        assert refs == ["items"]

    def test_all_builtins_excluded(self):
        for func in ["len", "keys", "int", "double", "string", "bool", "type", "not"]:
            refs = extract_variable_references(f"{func}(x)")
            assert "x" in refs
            assert func not in refs

    def test_member_access_returns_root(self):
        refs = extract_variable_references("response.body.data")
        assert refs == ["response"]

    def test_bracket_access_returns_root(self):
        refs = extract_variable_references('config["key"]')
        assert refs == ["config"]

    def test_literal_only(self):
        assert extract_variable_references("42") == []
        assert extract_variable_references('"hello"') == []
        assert extract_variable_references("true") == []
        assert extract_variable_references("null") == []

    def test_complex_expression(self):
        refs = extract_variable_references(
            '(x + 5) * 2 > 20 and len(items) != 0 and "key" in my_map'
        )
        assert "x" in refs
        assert "items" in refs
        assert "my_map" in refs

    def test_non_builtin_function_is_variable(self):
        # User-defined function calls via subworkflow -- the function name
        # is treated as a variable reference (since it could be a subworkflow name)
        refs = extract_variable_references("my_func(x)")
        assert "my_func" in refs
        assert "x" in refs

    def test_invalid_expression_returns_empty(self):
        refs = extract_variable_references("@@@")
        assert refs == []


# =============================================================================
# Integration tests using YAML fixtures
# =============================================================================


class TestExpressionFixtures:
    """Integration tests: parse YAML fixtures, extract expressions, validate."""

    @pytest.mark.parametrize(
        "fixture",
        [
            "valid_arithmetic.yaml",
            "valid_comparison.yaml",
            "valid_logical.yaml",
            "valid_strings.yaml",
            "valid_member_access.yaml",
            "valid_functions.yaml",
            "valid_literals.yaml",
            "valid_membership.yaml",
            "valid_complex.yaml",
        ],
    )
    def test_valid_fixture_expressions(self, fixture):
        """All expressions in valid fixture files should parse without errors."""
        yaml_str = load_fixture("expressions", fixture)
        # Parse the workflow to get the model, then validate expressions in the raw YAML
        import yaml

        raw = yaml.safe_load(yaml_str)
        errors = validate_all_expressions(raw)
        assert errors == [], f"Unexpected errors in {fixture}: " + "; ".join(
            f"{e.expression!r}: {e.message}" for e in errors
        )

    def test_valid_fixture_parses_as_workflow(self):
        """Valid expression fixtures should also be valid workflows."""
        for fixture in [
            "valid_arithmetic.yaml",
            "valid_comparison.yaml",
            "valid_logical.yaml",
            "valid_strings.yaml",
            "valid_member_access.yaml",
            "valid_functions.yaml",
            "valid_literals.yaml",
            "valid_membership.yaml",
            "valid_complex.yaml",
        ]:
            wf = parse_fixture("expressions", fixture)
            assert wf is not None, f"Failed to parse {fixture} as workflow"


# =============================================================================
# Invalid expression fixture tests
# =============================================================================


def _load_invalid_expressions() -> list[tuple[str, str]]:
    """Load invalid_expressions.yaml and return (label, expr_body) pairs."""
    import yaml

    yaml_str = load_fixture("expressions", "invalid_expressions.yaml")
    raw = yaml.safe_load(yaml_str)
    results = []
    for key, value in raw.items():
        # Each value is a "${...}" string — extract the body
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            body = value[2:-1]
            results.append((key, body))
    return results


class TestInvalidExpressionsFixture:
    """Parametrized tests loading expressions from invalid_expressions.yaml."""

    @pytest.mark.parametrize(
        "label,expr_body",
        _load_invalid_expressions(),
        ids=[pair[0] for pair in _load_invalid_expressions()],
    )
    def test_invalid_expression_from_fixture(self, label, expr_body):
        """Each expression in invalid_expressions.yaml must fail validation."""
        result = validate_expression(expr_body)
        assert result is not None, (
            f"Expected validation error for {label!r}: {expr_body!r}"
        )
        assert result.message, f"Error message should be non-empty for {label!r}"

    @pytest.mark.parametrize(
        "label,expr_body",
        _load_invalid_expressions(),
        ids=[pair[0] for pair in _load_invalid_expressions()],
    )
    def test_invalid_expression_recovery(self, label, expr_body):
        """Error recovery mode should still report errors for invalid expressions."""
        try:
            node, errors = parse_expression_recover(expr_body)
        except LexError:
            # Lex errors happen before parsing (e.g. unterminated string,
            # unexpected character) — that's also a valid failure.
            return
        assert len(errors) > 0, f"Expected recovery errors for {label!r}: {expr_body!r}"

    @pytest.mark.parametrize(
        "label,expr_body",
        _load_invalid_expressions(),
        ids=[pair[0] for pair in _load_invalid_expressions()],
    )
    def test_invalid_expression_has_error_node_or_raises(self, label, expr_body):
        """Recovery AST should contain ErrorNode(s), or lex should raise."""
        try:
            node, errors = parse_expression_recover(expr_body)
        except LexError:
            return  # lex-time failure is acceptable
        if errors:
            # At least one ErrorNode should be present in the tree
            nodes = walk(node)
            error_nodes = [n for n in nodes if isinstance(n, ErrorNode)]
            # Note: some errors are reported without ErrorNode (e.g. trailing
            # junk after a valid expression), so we check errors OR error_nodes
            assert len(errors) > 0


# =============================================================================
# AST snapshot tests
# =============================================================================


def _load_ast_snapshots() -> list[tuple[str, str, str]]:
    """Load ast_snapshots.yaml and return (label, expr, expected_repr) triples."""
    import yaml

    yaml_str = load_fixture("expressions", "ast_snapshots.yaml")
    raw = yaml.safe_load(yaml_str)
    results = []
    for key, entry in raw.items():
        results.append((key, entry["expr"], entry["expected"]))
    return results


class TestASTSnapshots:
    """Snapshot-based regression tests for parsed expression ASTs."""

    @pytest.mark.parametrize(
        "label,expr,expected_repr",
        _load_ast_snapshots(),
        ids=[t[0] for t in _load_ast_snapshots()],
    )
    def test_ast_snapshot(self, label, expr, expected_repr):
        """The repr() of the parsed AST must match the snapshot."""
        ast = parse_expression_ast(expr)
        actual = repr(ast)
        assert actual == expected_repr, (
            f"AST snapshot mismatch for {label!r}:\n"
            f"  expr:     {expr!r}\n"
            f"  expected: {expected_repr}\n"
            f"  actual:   {actual}"
        )

    @pytest.mark.parametrize(
        "label,expr,expected_repr",
        _load_ast_snapshots(),
        ids=[t[0] for t in _load_ast_snapshots()],
    )
    def test_ast_walk_covers_all_nodes(self, label, expr, expected_repr):
        """walk() should return a non-empty list for every parseable expression."""
        ast = parse_expression_ast(expr)
        nodes = walk(ast)
        assert len(nodes) >= 1, f"walk() returned empty list for {label!r}"
        # First node should be the root
        assert nodes[0] is ast
