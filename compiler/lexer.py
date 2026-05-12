# compiler/lexer.py
from __future__ import annotations

import re
import sys
from pathlib import Path

from compiler.tokens import KEYWORDS, Token, TokenType

# ── Three base regular expressions ──────────────────────────
RE1_NUMBER: str     = r"(?P<NUMBER>\d+(?:\.\d+)?)"
RE2_IDENTIFIER: str = r"(?P<IDENTIFIER>[a-zA-Z_][a-zA-Z0-9_]*)"
RE3_OPERATOR: str   = r"(?P<OPERATOR>[+\-*/()=;])"

# Combined master pattern — COMMENT must come before RE3_OPERATOR
# so that '//' is treated as a comment, not two DIVIDE tokens.
_MASTER: re.Pattern[str] = re.compile(
    RE1_NUMBER
    + "|" + RE2_IDENTIFIER
    + r"|(?P<COMMENT>//[^\n]*)"
    + "|" + RE3_OPERATOR
    + r"|(?P<WHITESPACE>[ \t\r\n]+)"
    + r"|(?P<INVALID>.)",
    re.DOTALL,
)

_OPERATOR_MAP: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.MULTIPLY,
    "/": TokenType.DIVIDE,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "=": TokenType.ASSIGN,
    ";": TokenType.SEMICOLON,
}


class LexerError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.line   = line
        self.column = column


class Lexer:
    """
    Phase 1 — Lexical Analysis.
    Tokenises source using the combined RE1 | RE2 | RE3 master pattern.
    Returns (tokens, errors) so all invalid characters are reported, not
    just the first.  Line + column tracking adopted from reference impl.
    """
    def __init__(self, source: str) -> None:
        self.source = source

    def tokenize(self) -> tuple[list[Token], list[LexerError]]:
        tokens: list[Token] = []
        errors: list[LexerError] = []
        line       = 1
        line_start = 0

        for match in _MASTER.finditer(self.source):
            kind  = match.lastgroup
            value = match.group()
            col   = match.start() - line_start + 1

            if kind == "COMMENT":
                continue

            if kind == "WHITESPACE":
                newlines = value.count("\n")
                if newlines:
                    line      += newlines
                    line_start = match.start() + value.rfind("\n") + 1
                continue

            if kind == "INVALID":
                errors.append(LexerError(
                    f"[Lexer Error] Unexpected character {value!r} "
                    f"at line {line}, column {col}",
                    line, col,
                ))
                continue

            if kind == "NUMBER":
                tokens.append(Token(TokenType.NUMBER, value, line, col))
            elif kind == "IDENTIFIER":
                token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
                tokens.append(Token(token_type, value, line, col))
            elif kind == "OPERATOR":
                tokens.append(Token(_OPERATOR_MAP[value], value, line, col))

        eof_col = len(self.source) - line_start + 1
        tokens.append(Token(TokenType.EOF, "", line, eof_col))
        return tokens, errors


def format_tokens(tokens: list[Token]) -> str:
    header  = f"  {'LINE:COL':<10} {'TYPE':<14} {'VALUE'}"
    divider = "  " + "-" * 38
    rows    = [header, divider]
    for tok in tokens:
        loc = f"{tok.line}:{tok.column}"
        rows.append(f"  {loc:<10} {tok.type.name:<14} {tok.value!r}")
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    path   = Path(argv[1]) if len(argv) > 1 else Path("examples/sample.expr")
    source = path.read_text(encoding="utf-8")
    tokens, errors = Lexer(source).tokenize()
    for err in errors:
        print(err, file=sys.stderr)
    print(format_tokens(tokens))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
