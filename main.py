#!/usr/bin/env python3
# main.py
# ─────────────────────────────────────────────────────────────
# Front-End Compiler — entry point
#
# Usage
# ─────
#   # Run all built-in test cases (both parsers):
#   python main.py
#
#   # Compile a single expression with the default (top-down) parser:
#   python main.py "x = 3 + 5 * 2"
#
#   # Compile with the bottom-up (shift-reduce) parser:
#   python main.py --bottom-up "x = 3 + 5 * 2"
#
#   # Compile a .expr file:
#   python main.py examples/sample.expr
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

from compiler.pipeline import compile_source


# ─────────────────────────────────────────────────────────────
# Built-in test suite
# Each tuple: (description, source, expect_error_in_phase)
# ─────────────────────────────────────────────────────────────
TEST_CASES: list[tuple[str, str]] = [
    # ── Valid inputs ──────────────────────────────────────
    ("Precedence: * before +",              "3 + 5 * 2"),
    ("Parentheses override precedence",     "(2 + 3) * 4"),
    ("Left-associativity of  -",            "10 - 4 - 2"),
    ("Left-associativity of  /",            "12 / 4 / 3"),
    ("Variable assignment",                 "x = 10"),
    ("Variable used in expression",         "x = 10; y = x + 5"),
    ("print() statement",                   "print(42)"),
    ("Comment is stripped",                 "1 + 2 // ignored"),
    ("Complex expression",                  "2 * 3 + 4 * 5"),
    # ── Error cases ───────────────────────────────────────
    ("LEXER  ERROR: invalid character",     "3 + @ 2"),
    ("PARSER ERROR: consecutive operators", "3 + * 2"),
    ("PARSER ERROR: unclosed parenthesis",  "(3 + 5"),
    ("PARSER ERROR: missing print paren",   "print 42"),
    ("SEMANTIC ERROR: division by zero",    "10 / 0"),
    ("SEMANTIC ERROR: undefined variable",  "z + 1"),
    ("SEMANTIC ERROR: use before assign",   "y + 1; y = 5"),
]


def main(argv: list[str]) -> int:
    use_bottom_up = "--bottom-up" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]

    if args:
        raw = args[0]
        path = Path(raw)
        if path.exists() and path.suffix == ".expr":
            source = path.read_text(encoding="utf-8")
            # Run each non-blank, non-comment line as its own statement
            compile_source(source, use_bottom_up=use_bottom_up)
        else:
            compile_source(raw, use_bottom_up=use_bottom_up)
        return 0

    # No arguments — run the full built-in test suite twice:
    # once with each parser so both are demonstrated.
    for parser_flag, label in [
        (False, "TOP-DOWN  (Recursive Descent, LL(1))"),
        (True,  "BOTTOM-UP (Shift-Reduce, operator-precedence)"),
    ]:
        print()
        print("*" * 64)
        print(f"  PARSER MODE: {label}")
        print("*" * 64)
        for description, source in TEST_CASES:
            print(f"\n  ▶  {description}")
            compile_source(source, use_bottom_up=parser_flag)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))   # pattern from reference impl.
