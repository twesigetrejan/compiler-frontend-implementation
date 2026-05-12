# compiler/tokens.py
# ─────────────────────────────────────────────────────────────
# Token types and the Token dataclass.
#
# Design notes (integrated from reference implementation):
#   • TokenType uses Enum + auto() — no magic numbers
#   • KEYWORDS dict maps identifier strings → keyword TokenTypes,
#     letting the lexer re-classify identifiers after RE2 matches
#   • Token is a frozen, slotted dataclass — immutable and memory-
#     efficient (adopted from the reference implementation)
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # ── RE1: numeric literals ──────────────────────────────
    NUMBER = auto()

    # ── RE2: identifiers & keywords ───────────────────────
    IDENTIFIER = auto()
    PRINT      = auto()   # keyword: print(expr)

    # ── RE3: operators & symbols ──────────────────────────
    PLUS      = auto()
    MINUS     = auto()
    MULTIPLY  = auto()
    DIVIDE    = auto()
    LPAREN    = auto()
    RPAREN    = auto()
    ASSIGN    = auto()
    SEMICOLON = auto()

    # ── Synthetic (not produced by any RE) ────────────────
    EOF = auto()


# Any identifier whose text appears here is reclassified
# to the corresponding keyword token type by the lexer.
KEYWORDS: dict[str, TokenType] = {
    "print": TokenType.PRINT,
}


@dataclass(frozen=True, slots=True)   # ← adopted from reference impl.
class Token:
    """A single lexical unit with its type, raw text, and source location."""
    type:   TokenType
    value:  str
    line:   int
    column: int

    def __repr__(self) -> str:
        return (
            f"Token({self.type.name}, {self.value!r}, "
            f"line={self.line}, col={self.column})"
        )
