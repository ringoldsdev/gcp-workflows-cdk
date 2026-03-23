"""Expression parser and validator for GCP Cloud Workflows ${...} expressions.

Implements a Pratt (top-down operator precedence) parser that validates the
syntax of expressions found inside ${...} wrappers, producing a lightweight
AST of dataclass nodes for downstream analysis and snapshot testing.

Grammar (informal):
    expression     -> or_expr
    or_expr        -> and_expr ("or" and_expr)*
    and_expr       -> membership (("and") membership)*
    membership     -> comparison ("in" comparison)?
    comparison     -> addition (("==" | "!=" | "<=" | ">=" | "<" | ">") addition)?
    addition       -> multiplication (("+" | "-") multiplication)*
    multiplication -> unary (("*" | "/" | "%") unary)*
    unary          -> "-" unary | "not" "(" expression ")" | primary_postfix
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
# AST node types
# =============================================================================


@dataclass
class NumberLiteral:
    """Integer or floating-point literal."""

    value: str
    pos: int


@dataclass
class StringLiteral:
    """String literal (quotes already removed)."""

    value: str
    pos: int


@dataclass
class BoolLiteral:
    """true / false literal."""

    value: bool
    pos: int


@dataclass
class NullLiteral:
    """null literal."""

    pos: int


@dataclass
class Identifier:
    """Variable or function name."""

    name: str
    pos: int


@dataclass
class UnaryOp:
    """Unary operator (e.g. -x, not(...))."""

    op: str
    operand: Node
    pos: int


@dataclass
class BinaryOp:
    """Binary operator (arithmetic, comparison, logical, membership)."""

    op: str
    left: Node
    right: Node
    pos: int


@dataclass
class MemberAccess:
    """Dot access: obj.field."""

    object: Node
    field: str
    pos: int


@dataclass
class IndexAccess:
    """Bracket access: obj[index]."""

    object: Node
    index: Node
    pos: int


@dataclass
class FunctionCall:
    """Function call: func(args...)."""

    function: Node
    args: list[Node]
    pos: int


@dataclass
class ListLiteral:
    """List literal: [a, b, c]."""

    elements: list[Node]
    pos: int


@dataclass
class MapEntry:
    """Single key-value pair in a map literal."""

    key: Node
    value: Node
    pos: int


@dataclass
class MapLiteral:
    """Map literal: {"a": 1, "b": 2}."""

    entries: list[MapEntry]
    pos: int


@dataclass
class ErrorNode:
    """Placeholder for a failed parse (error recovery)."""

    message: str
    pos: int
    children: list[Node] = field(default_factory=list)


# Union of all AST node types
Node = (
    NumberLiteral
    | StringLiteral
    | BoolLiteral
    | NullLiteral
    | Identifier
    | UnaryOp
    | BinaryOp
    | MemberAccess
    | IndexAccess
    | FunctionCall
    | ListLiteral
    | MapEntry
    | MapLiteral
    | ErrorNode
)


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


# ---------------------------------------------------------------------------
# Unified master regex – compiled once at module load time.
#
# Named groups are ordered by specificity (longest match first).  The
# ``re.finditer`` engine tries alternatives left-to-right, so two-char
# operators (==, !=, <=, >=) MUST precede their single-char prefixes.
#
# Strings use a regex that matches the full literal including escape
# sequences (``"(?:[^"\\]|\\.)*"`` and the single-quote variant).
# Unterminated strings are caught separately (the quote character won't
# match any named group and falls through to MISMATCH).
# ---------------------------------------------------------------------------
_TOKEN_PATTERNS: list[tuple[str, str]] = [
    # Whitespace (skipped)
    ("SKIP", r"\s+"),
    # String literals (full, including escapes)
    ("STRING_DQ", r'"(?:[^"\\]|\\.)*"'),
    ("STRING_SQ", r"'(?:[^'\\]|\\.)*'"),
    # Numbers – order: float variants before plain integer
    ("DOUBLE", r"\d+\.\d*|\.\d+"),
    ("INTEGER", r"\d+"),
    # Two-character operators (before single-char)
    ("EQ", r"=="),
    ("NEQ", r"!="),
    ("LTE", r"<="),
    ("GTE", r">="),
    # Single-character operators
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("SLASH", r"/"),
    ("PERCENT", r"%"),
    ("LT", r"<"),
    ("GT", r">"),
    # Delimiters
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("DOT", r"\."),
    ("COMMA", r","),
    ("COLON", r":"),
    # Identifiers / keywords (checked after operators)
    ("IDENT", r"[A-Za-z_][A-Za-z_0-9]*"),
    # Catch-all for unexpected characters
    ("MISMATCH", r"."),
]

_MASTER_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_PATTERNS)
)

# Mapping from master-regex group names to TokenType (excluding SKIP/MISMATCH)
_GROUP_TO_TYPE: dict[str, TokenType] = {
    "STRING_DQ": TokenType.STRING,
    "STRING_SQ": TokenType.STRING,
    "DOUBLE": TokenType.DOUBLE,
    "INTEGER": TokenType.INTEGER,
    "EQ": TokenType.EQ,
    "NEQ": TokenType.NEQ,
    "LTE": TokenType.LTE,
    "GTE": TokenType.GTE,
    "PLUS": TokenType.PLUS,
    "MINUS": TokenType.MINUS,
    "STAR": TokenType.STAR,
    "SLASH": TokenType.SLASH,
    "PERCENT": TokenType.PERCENT,
    "LT": TokenType.LT,
    "GT": TokenType.GT,
    "LPAREN": TokenType.LPAREN,
    "RPAREN": TokenType.RPAREN,
    "LBRACKET": TokenType.LBRACKET,
    "RBRACKET": TokenType.RBRACKET,
    "LBRACE": TokenType.LBRACE,
    "RBRACE": TokenType.RBRACE,
    "DOT": TokenType.DOT,
    "COMMA": TokenType.COMMA,
    "COLON": TokenType.COLON,
    "IDENT": TokenType.IDENT,
}

# Escape sequences recognized inside string literals
_ESCAPE_MAP: dict[str, str] = {
    "n": "\n",
    "t": "\t",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


def _decode_string(raw: str, pos: int) -> str:
    """Decode escape sequences in a matched string literal.

    *raw* is the regex-matched text **including** surrounding quotes.
    Returns the unescaped content (quotes stripped).
    """
    inner = raw[1:-1]  # strip surrounding quotes
    result: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\":
            if i + 1 >= len(inner):
                raise LexError(
                    f"Unterminated escape at position {pos + i + 1}", pos + i + 1
                )
            nxt = inner[i + 1]
            result.append(_ESCAPE_MAP.get(nxt, nxt))
            i += 2
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def tokenize(source: str) -> list[Token]:
    """Tokenize a Cloud Workflows expression (content inside ${...}).

    Uses a single compiled master regex with ``re.finditer`` for a fast,
    single-pass scan through the C-level regex engine.
    """
    tokens: list[Token] = []

    for m in _MASTER_RE.finditer(source):
        kind: str = m.lastgroup or "MISMATCH"
        text = m.group()
        pos = m.start()

        if kind == "SKIP":
            continue

        if kind == "MISMATCH":
            # Distinguish unterminated strings from truly unexpected chars
            if text in ('"', "'"):
                raise LexError(f"Unterminated string starting at position {pos}", pos)
            raise LexError(f"Unexpected character {text!r} at position {pos}", pos)

        if kind in ("STRING_DQ", "STRING_SQ"):
            tokens.append(Token(TokenType.STRING, _decode_string(text, pos), pos))
            continue

        tt = _GROUP_TO_TYPE[kind]

        # Resolve identifiers vs keywords
        if tt is TokenType.IDENT:
            tt = KEYWORDS.get(text, TokenType.IDENT)

        tokens.append(Token(tt, text, pos))

    tokens.append(Token(TokenType.EOF, "", len(source)))
    return tokens


# =============================================================================
# Pratt parser  (top-down operator precedence)
# =============================================================================

# ---------------------------------------------------------------------------
# Binding power table
#
# Each infix/postfix operator maps to (left_bp, right_bp).  Left-associative
# ops have right_bp = left_bp + 1; right-associative: right_bp = left_bp.
# Postfix operators (. [] ()) have the highest binding power and are handled
# as LED (left denotation) entries inside the main Pratt loop.
# ---------------------------------------------------------------------------

_BP_OR = 2
_BP_AND = 4
_BP_MEMBERSHIP = 6
_BP_COMPARISON = 8
_BP_ADDITION = 10
_BP_MULTIPLICATION = 12
_BP_UNARY = 14  # prefix operators
_BP_POSTFIX = 16  # . [] ()

# infix token → (left_bp, right_bp, op_string)
_INFIX_BP: dict[TokenType, tuple[int, int, str]] = {
    TokenType.OR: (_BP_OR, _BP_OR + 1, "or"),
    TokenType.AND: (_BP_AND, _BP_AND + 1, "and"),
    TokenType.IN: (_BP_MEMBERSHIP, _BP_MEMBERSHIP + 1, "in"),
    TokenType.EQ: (_BP_COMPARISON, _BP_COMPARISON + 1, "=="),
    TokenType.NEQ: (_BP_COMPARISON, _BP_COMPARISON + 1, "!="),
    TokenType.LT: (_BP_COMPARISON, _BP_COMPARISON + 1, "<"),
    TokenType.LTE: (_BP_COMPARISON, _BP_COMPARISON + 1, "<="),
    TokenType.GT: (_BP_COMPARISON, _BP_COMPARISON + 1, ">"),
    TokenType.GTE: (_BP_COMPARISON, _BP_COMPARISON + 1, ">="),
    TokenType.PLUS: (_BP_ADDITION, _BP_ADDITION + 1, "+"),
    TokenType.MINUS: (_BP_ADDITION, _BP_ADDITION + 1, "-"),
    TokenType.STAR: (_BP_MULTIPLICATION, _BP_MULTIPLICATION + 1, "*"),
    TokenType.SLASH: (_BP_MULTIPLICATION, _BP_MULTIPLICATION + 1, "/"),
    TokenType.PERCENT: (_BP_MULTIPLICATION, _BP_MULTIPLICATION + 1, "%"),
}

# Postfix tokens handled in the LED portion of the Pratt loop
_POSTFIX_TOKENS: set[TokenType] = {TokenType.DOT, TokenType.LBRACKET, TokenType.LPAREN}

# Non-chaining operators: only one application allowed at this precedence
_NON_CHAINING: set[int] = {_BP_COMPARISON, _BP_MEMBERSHIP}


class ExpressionParser:
    """Pratt (top-down operator precedence) parser for Cloud Workflows expressions.

    Produces a lightweight AST of dataclass nodes.  Supports error recovery:
    when *recover=True*, the parser emits :class:`ErrorNode` placeholders
    instead of raising on every fault, attempting to continue and report
    multiple errors in a single pass.
    """

    def __init__(self, tokens: list[Token], *, recover: bool = False):
        self.tokens = tokens
        self.pos = 0
        self.recover = recover
        self.errors: list[ParseError] = []

    # -- token helpers -------------------------------------------------------

    def peek(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # always return EOF
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:  # don't advance past EOF
            self.pos += 1
        return tok

    def expect(self, tt: TokenType) -> Token:
        tok = self.peek()
        if tok.type != tt:
            err = ParseError(
                f"Expected {tt.name} but got {tok.type.name} ({tok.value!r}) "
                f"at position {tok.pos}",
                tok.pos,
            )
            if self.recover:
                self.errors.append(err)
                return self._synchronize(tt)
            raise err
        return self.advance()

    def at(self, *types: TokenType) -> bool:
        return self.peek().type in types

    # -- error recovery helpers -----------------------------------------------

    _SYNC_TOKENS: set[TokenType] = {
        TokenType.RPAREN,
        TokenType.RBRACKET,
        TokenType.RBRACE,
        TokenType.COMMA,
        TokenType.COLON,
        TokenType.EOF,
    }

    def _synchronize(self, expected: TokenType) -> Token:
        """Skip tokens until *expected* or a synchronization token is found."""
        while not self.at(expected, TokenType.EOF):
            if self.peek().type in self._SYNC_TOKENS:
                break
            self.advance()
        if self.at(expected):
            return self.advance()
        return Token(expected, "", self.peek().pos)

    def _error_node(self, err: ParseError) -> ErrorNode:
        """Record an error and return a placeholder AST node."""
        self.errors.append(err)
        return ErrorNode(message=str(err), pos=err.pos)

    # -- top-level entry point -----------------------------------------------

    def parse(self) -> Node:
        """Parse the full expression and ensure we consume everything."""
        node = self.parse_expression(0)
        if self.peek().type != TokenType.EOF:
            tok = self.peek()
            err = ParseError(
                f"Unexpected token {tok.type.name} ({tok.value!r}) "
                f"at position {tok.pos} -- expected end of expression",
                tok.pos,
            )
            if self.recover:
                self.errors.append(err)
                while not self.at(TokenType.EOF):
                    self.advance()
            else:
                raise err
        return node

    # -- Pratt core -----------------------------------------------------------

    def parse_expression(self, min_bp: int) -> Node:
        """Core Pratt loop: NUD then LED while binding power allows.

        Postfix operators (``.``, ``[``, ``(``) are integrated into the loop
        at ``_BP_POSTFIX`` so that expressions like ``f(a + b)`` correctly
        parse ``a + b`` as the full argument.

        Non-chaining operators (comparison, membership) are allowed at most
        once per call: after one fires, its precedence is recorded in
        *used_non_chain* to prevent a second match at the same level,
        without blocking lower-precedence operators like ``and`` / ``or``.
        """
        lhs = self._nud()

        # Track which non-chaining BP levels have already been used in THIS
        # invocation, so we can reject a second operator at the same level.
        used_non_chain: set[int] = set()

        while True:
            tok = self.peek()

            # --- Postfix operators (highest precedence) ---
            if tok.type in _POSTFIX_TOKENS:
                if _BP_POSTFIX < min_bp:
                    break
                lhs = self._led_postfix(lhs)
                continue

            # --- Infix binary operators ---
            info = _INFIX_BP.get(tok.type)
            if info is None:
                break
            left_bp, right_bp, op_str = info
            if left_bp < min_bp:
                break

            # Non-chaining: reject a second operator at the same level
            if left_bp in _NON_CHAINING:
                if left_bp in used_non_chain:
                    break
                used_non_chain.add(left_bp)

            op_tok = self.advance()
            rhs = self.parse_expression(right_bp)
            lhs = BinaryOp(op=op_str, left=lhs, right=rhs, pos=op_tok.pos)

        return lhs

    # -- NUD (null denotation / prefix) ---------------------------------------

    def _nud(self) -> Node:
        """Parse a prefix token (literal, identifier, unary op, grouping)."""
        tok = self.peek()

        # Unary minus — parse operand at unary precedence
        if tok.type == TokenType.MINUS:
            op_tok = self.advance()
            operand = self.parse_expression(_BP_UNARY)
            return UnaryOp(op="-", operand=operand, pos=op_tok.pos)

        # Numeric literals
        if tok.type == TokenType.INTEGER:
            self.advance()
            return NumberLiteral(value=tok.value, pos=tok.pos)
        if tok.type == TokenType.DOUBLE:
            self.advance()
            return NumberLiteral(value=tok.value, pos=tok.pos)

        # String literal
        if tok.type == TokenType.STRING:
            self.advance()
            return StringLiteral(value=tok.value, pos=tok.pos)

        # Boolean / null
        if tok.type == TokenType.TRUE:
            self.advance()
            return BoolLiteral(value=True, pos=tok.pos)
        if tok.type == TokenType.FALSE:
            self.advance()
            return BoolLiteral(value=False, pos=tok.pos)
        if tok.type == TokenType.NULL:
            self.advance()
            return NullLiteral(pos=tok.pos)

        # Identifier
        if tok.type == TokenType.IDENT:
            self.advance()
            return Identifier(name=tok.value, pos=tok.pos)

        # ``not`` keyword used as identifier-like (function call via postfix)
        if tok.type == TokenType.NOT:
            self.advance()
            return Identifier(name="not", pos=tok.pos)

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self.advance()
            node = self.parse_expression(0)
            self.expect(TokenType.RPAREN)
            return node

        # List literal
        if tok.type == TokenType.LBRACKET:
            return self._parse_list()

        # Map literal
        if tok.type == TokenType.LBRACE:
            return self._parse_map()

        err = ParseError(
            f"Unexpected token {tok.type.name} ({tok.value!r}) at position {tok.pos}",
            tok.pos,
        )
        if self.recover:
            self.advance()
            return self._error_node(err)
        raise err

    # -- LED for postfix operators -------------------------------------------

    def _led_postfix(self, lhs: Node) -> Node:
        """Handle a single postfix operator: ``.field``, ``[idx]``, ``(args)``."""
        if self.at(TokenType.DOT):
            dot = self.advance()
            name_tok = self.expect(TokenType.IDENT)
            return MemberAccess(object=lhs, field=name_tok.value, pos=dot.pos)
        if self.at(TokenType.LBRACKET):
            bracket = self.advance()
            index = self.parse_expression(0)
            self.expect(TokenType.RBRACKET)
            return IndexAccess(object=lhs, index=index, pos=bracket.pos)
        if self.at(TokenType.LPAREN):
            paren = self.advance()
            args: list[Node] = []
            if not self.at(TokenType.RPAREN):
                args = self._parse_arguments()
            self.expect(TokenType.RPAREN)
            return FunctionCall(function=lhs, args=args, pos=paren.pos)
        return lhs  # unreachable

    # -- Compound literals and arguments -------------------------------------

    def _parse_list(self) -> ListLiteral:
        tok = self.advance()  # consume [
        elements: list[Node] = []
        if not self.at(TokenType.RBRACKET):
            elements.append(self.parse_expression(0))
            while self.at(TokenType.COMMA):
                self.advance()
                if self.at(TokenType.RBRACKET):
                    break  # trailing comma
                elements.append(self.parse_expression(0))
        self.expect(TokenType.RBRACKET)
        return ListLiteral(elements=elements, pos=tok.pos)

    def _parse_map(self) -> MapLiteral:
        tok = self.advance()  # consume {
        entries: list[MapEntry] = []
        if not self.at(TokenType.RBRACE):
            entries.append(self._parse_map_entry())
            while self.at(TokenType.COMMA):
                self.advance()
                if self.at(TokenType.RBRACE):
                    break  # trailing comma
                entries.append(self._parse_map_entry())
        self.expect(TokenType.RBRACE)
        return MapLiteral(entries=entries, pos=tok.pos)

    def _parse_map_entry(self) -> MapEntry:
        key = self.parse_expression(0)
        colon = self.expect(TokenType.COLON)
        value = self.parse_expression(0)
        return MapEntry(key=key, value=value, pos=colon.pos)

    def _parse_arguments(self) -> list[Node]:
        args: list[Node] = [self.parse_expression(0)]
        while self.at(TokenType.COMMA):
            self.advance()
            if self.at(TokenType.RPAREN):
                break  # trailing comma
            args.append(self.parse_expression(0))
        return args


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


def parse_expression_ast(expr_body: str) -> Node:
    """Parse an expression body into an AST.

    Raises LexError or ParseError on invalid input.
    """
    tokens = tokenize(expr_body)
    parser = ExpressionParser(tokens)
    return parser.parse()


def parse_expression_recover(expr_body: str) -> tuple[Node, list[ExpressionError]]:
    """Parse an expression with error recovery enabled.

    Returns ``(ast, errors)`` where *errors* may be non-empty even when the
    AST is returned (it will contain :class:`ErrorNode` placeholders).
    """
    tokens = tokenize(expr_body)
    parser = ExpressionParser(tokens, recover=True)
    node = parser.parse()
    errors = [
        ExpressionError(expression=expr_body, message=str(e), pos=e.pos)
        for e in parser.errors
    ]
    return node, errors


def validate_expression(expr_body: str) -> Optional[ExpressionError]:
    """Validate a single expression body (the content inside ${...}).

    Returns None if valid, or an ExpressionError if invalid.
    """
    try:
        parse_expression_ast(expr_body)
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


# =============================================================================
# AST visitor infrastructure
# =============================================================================


def walk(node: Node) -> list[Node]:
    """Yield all nodes in the AST in depth-first pre-order."""
    result: list[Node] = [node]
    if isinstance(node, UnaryOp):
        result.extend(walk(node.operand))
    elif isinstance(node, BinaryOp):
        result.extend(walk(node.left))
        result.extend(walk(node.right))
    elif isinstance(node, MemberAccess):
        result.extend(walk(node.object))
    elif isinstance(node, IndexAccess):
        result.extend(walk(node.object))
        result.extend(walk(node.index))
    elif isinstance(node, FunctionCall):
        result.extend(walk(node.function))
        for arg in node.args:
            result.extend(walk(arg))
    elif isinstance(node, ListLiteral):
        for elem in node.elements:
            result.extend(walk(elem))
    elif isinstance(node, MapLiteral):
        for entry in node.entries:
            result.extend(walk(entry))
    elif isinstance(node, MapEntry):
        result.extend(walk(node.key))
        result.extend(walk(node.value))
    elif isinstance(node, ErrorNode):
        for child in node.children:
            result.extend(walk(child))
    return result


# Expression-context built-in functions (not variables)
# Canonical set lives in consts.py; import here to keep a single source of truth.
from .consts import EXPRESSION_BUILTINS as _BUILTINS  # noqa: E402


def extract_variable_references(expr_body: str) -> list[str]:
    """Extract top-level variable names referenced in an expression.

    Uses AST traversal for accuracy.  Built-in function names are excluded;
    member-access fields (the ``y`` in ``x.y``) are excluded; the root
    object in a chain (``x`` in ``x.y.z[0]``) is included.

    For example:
        "x + y.field" -> ["x", "y"]
        "len(items)" -> ["items"]
        "a[0].b + c" -> ["a", "c"]
        '"literal"' -> []
    """
    try:
        ast = parse_expression_ast(expr_body)
    except (LexError, ParseError):
        return []

    refs: list[str] = []
    _collect_refs(ast, None, refs)
    return refs


def _collect_refs(node: Node, parent: Node | None, refs: list[str]) -> None:
    """Recursively collect root-level variable references from the AST."""
    if isinstance(node, Identifier):
        refs.append(node.name)
    elif isinstance(node, UnaryOp):
        _collect_refs(node.operand, node, refs)
    elif isinstance(node, BinaryOp):
        _collect_refs(node.left, node, refs)
        _collect_refs(node.right, node, refs)
    elif isinstance(node, MemberAccess):
        # Only collect from the object side (the root of the chain)
        _collect_refs(node.object, node, refs)
    elif isinstance(node, IndexAccess):
        _collect_refs(node.object, node, refs)
        _collect_refs(node.index, node, refs)
    elif isinstance(node, FunctionCall):
        # If the function is a builtin name, skip collecting it as a variable
        # but still collect from the arguments.
        if isinstance(node.function, Identifier) and node.function.name in _BUILTINS:
            for arg in node.args:
                _collect_refs(arg, node, refs)
        else:
            _collect_refs(node.function, node, refs)
            for arg in node.args:
                _collect_refs(arg, node, refs)
    elif isinstance(node, ListLiteral):
        for elem in node.elements:
            _collect_refs(elem, node, refs)
    elif isinstance(node, MapLiteral):
        for entry in node.entries:
            _collect_refs(entry, node, refs)
    elif isinstance(node, MapEntry):
        _collect_refs(node.key, node, refs)
        _collect_refs(node.value, node, refs)
    elif isinstance(node, ErrorNode):
        for child in node.children:
            _collect_refs(child, node, refs)
