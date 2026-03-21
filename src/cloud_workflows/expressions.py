"""Expression parser and validator for GCP Cloud Workflows ${...} expressions.

Implements a recursive-descent parser that validates the syntax of expressions
found inside ${...} wrappers. Does NOT evaluate expressions -- only checks that
they are syntactically valid according to the GCP Cloud Workflows expression spec.

Grammar (informal):
    expression     -> or_expr
    or_expr        -> and_expr ("or" and_expr)*
    and_expr       -> membership (("and") membership)*
    membership     -> comparison ("in" comparison)?
    comparison     -> addition (("==" | "!=" | "<=" | ">=" | "<" | ">") addition)?
    addition       -> multiplication (("+" | "-") multiplication)*
    multiplication -> unary (("*" | "/" | "%") unary)*
    unary          -> "-" unary | primary_postfix
    primary_postfix-> primary (accessor)*
    accessor       -> "." IDENT | "[" expression "]" | "(" arguments? ")"
    primary        -> NUMBER | STRING | "true" | "false" | "null"
                    | IDENT
                    | "(" expression ")"
                    | "[" list_items? "]"
                    | "{" map_items? "}"
    list_items     -> expression ("," expression)* ","?
    map_items      -> map_entry ("," map_entry)* ","?
    map_entry      -> expression ":" expression
    arguments      -> expression ("," expression)* ","?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


# =============================================================================
# Token types
# =============================================================================


class TokenType(Enum):
    # Literals
    INTEGER = auto()
    DOUBLE = auto()
    STRING = auto()

    # Identifiers and keywords
    IDENT = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    AND = auto()
    OR = auto()
    IN = auto()
    NOT = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()  # ==
    NEQ = auto()  # !=
    LT = auto()  # <
    LTE = auto()  # <=
    GT = auto()  # >
    GTE = auto()  # >=

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    DOT = auto()
    COMMA = auto()
    COLON = auto()

    # End of expression
    EOF = auto()


KEYWORDS = {
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "in": TokenType.IN,
    "not": TokenType.NOT,
}


# =============================================================================
# Token
# =============================================================================


@dataclass
class Token:
    type: TokenType
    value: str
    pos: int  # character offset in source


# =============================================================================
# Lexer
# =============================================================================


class LexError(Exception):
    """Raised when tokenization fails."""

    def __init__(self, message: str, pos: int):
        self.pos = pos
        super().__init__(message)


class ParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, pos: int):
        self.pos = pos
        super().__init__(message)


# Regex patterns for tokens, tried in order
_NUMBER_RE = re.compile(r"(\d+\.\d*|\.\d+|\d+)")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_WHITESPACE_RE = re.compile(r"\s+")


def _lex_string(source: str, pos: int) -> tuple[Token, int]:
    """Lex a string literal starting at pos (which must be ' or ")."""
    quote = source[pos]
    result: list[str] = []
    i = pos + 1
    while i < len(source):
        ch = source[i]
        if ch == "\\":
            if i + 1 >= len(source):
                raise LexError(f"Unterminated escape at position {i}", i)
            next_ch = source[i + 1]
            escape_map = {"n": "\n", "t": "\t", "\\": "\\", "'": "'", '"': '"'}
            if next_ch in escape_map:
                result.append(escape_map[next_ch])
                i += 2
            else:
                # Allow unknown escapes to pass through
                result.append(next_ch)
                i += 2
        elif ch == quote:
            return Token(TokenType.STRING, "".join(result), pos), i + 1
        else:
            result.append(ch)
            i += 1
    raise LexError(f"Unterminated string starting at position {pos}", pos)


def tokenize(source: str) -> list[Token]:
    """Tokenize a Cloud Workflows expression (content inside ${...})."""
    tokens: list[Token] = []
    i = 0
    length = len(source)

    while i < length:
        # Skip whitespace
        m = _WHITESPACE_RE.match(source, i)
        if m:
            i = m.end()
            continue

        ch = source[i]

        # Two-character operators
        if i + 1 < length:
            two = source[i : i + 2]
            if two == "==":
                tokens.append(Token(TokenType.EQ, "==", i))
                i += 2
                continue
            elif two == "!=":
                tokens.append(Token(TokenType.NEQ, "!=", i))
                i += 2
                continue
            elif two == "<=":
                tokens.append(Token(TokenType.LTE, "<=", i))
                i += 2
                continue
            elif two == ">=":
                tokens.append(Token(TokenType.GTE, ">=", i))
                i += 2
                continue

        # Single-character operators and delimiters
        single_map = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
            "<": TokenType.LT,
            ">": TokenType.GT,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            ".": TokenType.DOT,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
        }
        if ch in single_map:
            tokens.append(Token(single_map[ch], ch, i))
            i += 1
            continue

        # String literals
        if ch in ('"', "'"):
            tok, i = _lex_string(source, i)
            tokens.append(tok)
            continue

        # Numbers
        m = _NUMBER_RE.match(source, i)
        if m and (not source[i].isalpha()):
            num_str = m.group(0)
            if "." in num_str:
                tokens.append(Token(TokenType.DOUBLE, num_str, i))
            else:
                tokens.append(Token(TokenType.INTEGER, num_str, i))
            i = m.end()
            continue

        # Identifiers and keywords
        m = _IDENT_RE.match(source, i)
        if m:
            word = m.group(0)
            tt = KEYWORDS.get(word, TokenType.IDENT)
            tokens.append(Token(tt, word, i))
            i = m.end()
            continue

        raise LexError(f"Unexpected character {ch!r} at position {i}", i)

    tokens.append(Token(TokenType.EOF, "", length))
    return tokens


# =============================================================================
# Parser
# =============================================================================


class ExpressionParser:
    """Recursive-descent parser for Cloud Workflows expressions."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, tt: TokenType) -> Token:
        tok = self.peek()
        if tok.type != tt:
            raise ParseError(
                f"Expected {tt.name} but got {tok.type.name} ({tok.value!r}) "
                f"at position {tok.pos}",
                tok.pos,
            )
        return self.advance()

    def at(self, *types: TokenType) -> bool:
        return self.peek().type in types

    # -- Grammar rules -------------------------------------------------------

    def parse(self) -> None:
        """Parse the full expression and ensure we consume everything."""
        self.expression()
        if self.peek().type != TokenType.EOF:
            tok = self.peek()
            raise ParseError(
                f"Unexpected token {tok.type.name} ({tok.value!r}) "
                f"at position {tok.pos} -- expected end of expression",
                tok.pos,
            )

    def expression(self) -> None:
        self.or_expr()

    def or_expr(self) -> None:
        self.and_expr()
        while self.at(TokenType.OR):
            self.advance()
            self.and_expr()

    def and_expr(self) -> None:
        self.membership()
        while self.at(TokenType.AND):
            self.advance()
            self.membership()

    def membership(self) -> None:
        self.comparison()
        if self.at(TokenType.IN):
            self.advance()
            self.comparison()

    def comparison(self) -> None:
        self.addition()
        if self.at(
            TokenType.EQ,
            TokenType.NEQ,
            TokenType.LT,
            TokenType.LTE,
            TokenType.GT,
            TokenType.GTE,
        ):
            self.advance()
            self.addition()

    def addition(self) -> None:
        self.multiplication()
        while self.at(TokenType.PLUS, TokenType.MINUS):
            self.advance()
            self.multiplication()

    def multiplication(self) -> None:
        self.unary()
        while self.at(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            self.advance()
            self.unary()

    def unary(self) -> None:
        if self.at(TokenType.MINUS):
            self.advance()
            self.unary()
        else:
            self.primary_postfix()

    def primary_postfix(self) -> None:
        self.primary()
        while True:
            if self.at(TokenType.DOT):
                self.advance()
                self.expect(TokenType.IDENT)
            elif self.at(TokenType.LBRACKET):
                self.advance()
                self.expression()
                self.expect(TokenType.RBRACKET)
            elif self.at(TokenType.LPAREN):
                self.advance()
                if not self.at(TokenType.RPAREN):
                    self.arguments()
                self.expect(TokenType.RPAREN)
            else:
                break

    def primary(self) -> None:
        tok = self.peek()

        # Numeric literals
        if tok.type in (TokenType.INTEGER, TokenType.DOUBLE):
            self.advance()
            return

        # String literal
        if tok.type == TokenType.STRING:
            self.advance()
            return

        # Boolean / null
        if tok.type in (TokenType.TRUE, TokenType.FALSE, TokenType.NULL):
            self.advance()
            return

        # Identifier (variable name or function name -- call is handled in postfix)
        if tok.type == TokenType.IDENT:
            self.advance()
            return

        # `not` keyword used as function: not(...)
        if tok.type == TokenType.NOT:
            self.advance()
            return

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self.advance()
            self.expression()
            self.expect(TokenType.RPAREN)
            return

        # List literal
        if tok.type == TokenType.LBRACKET:
            self.advance()
            if not self.at(TokenType.RBRACKET):
                self.list_items()
            self.expect(TokenType.RBRACKET)
            return

        # Map literal
        if tok.type == TokenType.LBRACE:
            self.advance()
            if not self.at(TokenType.RBRACE):
                self.map_items()
            self.expect(TokenType.RBRACE)
            return

        raise ParseError(
            f"Unexpected token {tok.type.name} ({tok.value!r}) at position {tok.pos}",
            tok.pos,
        )

    def list_items(self) -> None:
        self.expression()
        while self.at(TokenType.COMMA):
            self.advance()
            # Allow trailing comma
            if self.at(TokenType.RBRACKET):
                break
            self.expression()

    def map_items(self) -> None:
        self.map_entry()
        while self.at(TokenType.COMMA):
            self.advance()
            # Allow trailing comma
            if self.at(TokenType.RBRACE):
                break
            self.map_entry()

    def map_entry(self) -> None:
        self.expression()
        self.expect(TokenType.COLON)
        self.expression()

    def arguments(self) -> None:
        self.expression()
        while self.at(TokenType.COMMA):
            self.advance()
            # Allow trailing comma
            if self.at(TokenType.RPAREN):
                break
            self.expression()


# =============================================================================
# Public API
# =============================================================================

# Pattern to find ${...} expressions in strings
_EXPR_PATTERN = re.compile(r"\$\{(.+?)\}", re.DOTALL)


# More robust: match ${...} with proper brace nesting
def _extract_expressions(value: str) -> list[tuple[str, int]]:
    """Extract expression bodies from a string containing ${...} wrappers.

    Returns list of (expression_body, start_offset) tuples.
    Handles nested braces correctly.
    """
    results: list[tuple[str, int]] = []
    i = 0
    while i < len(value):
        if value[i] == "$" and i + 1 < len(value) and value[i + 1] == "{":
            start = i
            # Find matching closing brace, respecting nesting and strings
            depth = 1
            j = i + 2
            while j < len(value) and depth > 0:
                ch = value[j]
                if ch in ('"', "'"):
                    # Skip string
                    quote = ch
                    j += 1
                    while j < len(value):
                        if value[j] == "\\" and j + 1 < len(value):
                            j += 2
                            continue
                        if value[j] == quote:
                            j += 1
                            break
                        j += 1
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                j += 1
            if depth == 0:
                body = value[start + 2 : j - 1]
                results.append((body, start + 2))
            i = j
        else:
            i += 1
    return results


@dataclass
class ExpressionError:
    """A single expression validation error."""

    expression: str
    message: str
    pos: Optional[int] = None


def validate_expression(expr_body: str) -> Optional[ExpressionError]:
    """Validate a single expression body (the content inside ${...}).

    Returns None if valid, or an ExpressionError if invalid.
    """
    try:
        tokens = tokenize(expr_body)
        parser = ExpressionParser(tokens)
        parser.parse()
        return None
    except (LexError, ParseError) as e:
        return ExpressionError(
            expression=expr_body,
            message=str(e),
            pos=getattr(e, "pos", None),
        )


def extract_expression_strings(value: Any) -> list[str]:
    """Extract all ${...} expression bodies from a value (recursively).

    Handles strings, lists, and dicts. Returns the inner expression bodies
    (without the ${} wrapper).
    """
    results: list[str] = []
    if isinstance(value, str):
        for body, _ in _extract_expressions(value):
            results.append(body)
    elif isinstance(value, list):
        for item in value:
            results.extend(extract_expression_strings(item))
    elif isinstance(value, dict):
        for v in value.values():
            results.extend(extract_expression_strings(v))
    return results


def validate_all_expressions(value: Any) -> list[ExpressionError]:
    """Find and validate all ${...} expressions in a value tree.

    Returns a list of ExpressionError for any invalid expressions.
    """
    errors: list[ExpressionError] = []
    for body in extract_expression_strings(value):
        err = validate_expression(body)
        if err is not None:
            errors.append(err)
    return errors


def extract_variable_references(expr_body: str) -> list[str]:
    """Extract top-level variable names referenced in an expression.

    This is a best-effort extraction for use by variable tracking.
    Returns a list of identifier names (the root variable name before
    any dot/bracket access).

    For example:
        "x + y.field" -> ["x", "y"]
        "len(items)" -> ["items"]
        "a[0].b + c" -> ["a", "c"]
        '"literal"' -> []
    """
    try:
        tokens = tokenize(expr_body)
    except LexError:
        return []

    refs: list[str] = []
    # Expression-context built-in functions (not variables)
    builtins = {"len", "keys", "int", "double", "string", "bool", "type", "not"}

    for i, tok in enumerate(tokens):
        if tok.type == TokenType.IDENT:
            # Check if it's a function call (followed by '(')
            if i + 1 < len(tokens) and tokens[i + 1].type == TokenType.LPAREN:
                if tok.value in builtins:
                    continue  # skip built-in function names
            # Check if it's preceded by a dot (member access, not a root variable)
            if i > 0 and tokens[i - 1].type == TokenType.DOT:
                continue
            refs.append(tok.value)

    return refs
