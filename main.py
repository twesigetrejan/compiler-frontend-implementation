#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# ─────────────────────────────────────────────────────────────
# Front-End Compiler — entry point
#
# Usage
# ─────
#   # Run all built-in test cases -> saves compiler_report.html:
#   python main.py
#
#   # Compile ONE expression -> saves compiler_report.html for it:
#   python main.py "x = 3 + 5 * 2"
#
#   # Same with the bottom-up (shift-reduce) parser:
#   python main.py --bottom-up "x = 3 + 5 * 2"
#
#   # Both parsers side-by-side for one expression:
#   python main.py --both "3 + 5 * 2"
#
#   # Compile a .expr file -> saves compiler_report.html for it:
#   python main.py examples/sample.expr
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

from compiler.pipeline import compile_source
from compiler.report import generate_report


# ─────────────────────────────────────────────────────────────
# Built-in test suite
# Each tuple: (description, source)
# ─────────────────────────────────────────────────────────────
TEST_CASES: list[tuple[str, str]] = [
    # -- Valid inputs --
    ("Precedence: * before +",              "3 + 5 * 2"),
    ("Parentheses override precedence",     "(2 + 3) * 4"),
    ("Left-associativity of  -",            "10 - 4 - 2"),
    ("Left-associativity of  /",            "12 / 4 / 3"),
    ("Variable assignment",                 "x = 10"),
    ("Variable used in expression",         "x = 10; y = x + 5"),
    ("print() statement",                   "print(42)"),
    ("Comment is stripped",                 "1 + 2 // ignored"),
    ("Complex expression",                  "2 * 3 + 4 * 5"),
    # -- Error cases --
    ("LEXER  ERROR: invalid character",     "3 + @ 2"),
    ("PARSER ERROR: consecutive operators", "3 + * 2"),
    ("PARSER ERROR: unclosed parenthesis",  "(3 + 5"),
    ("PARSER ERROR: missing print paren",   "print 42"),
    ("SEMANTIC ERROR: division by zero",    "10 / 0"),
    ("SEMANTIC ERROR: undefined variable",  "z + 1"),
    ("SEMANTIC ERROR: use before assign",   "y + 1; y = 5"),
]


# ─────────────────────────────────────────────────────────────
# Report helper
# ─────────────────────────────────────────────────────────────

def _save_report(cases: list[tuple[str, str]], label: str = "") -> None:
    """Generate compiler_report.html for the given cases and print the path."""
    report_path = Path("compiler_report.html")
    try:
        saved = generate_report(cases, report_path)
        print()
        print("=" * 64)
        if label:
            print(f"  {label}")
        print(f"  HTML report saved -> {saved.resolve()}")
        print("  Open compiler_report.html in your browser.")
        print("=" * 64)
    except Exception as exc:
        print(f"\n  [Report] Could not generate HTML report: {exc}")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    use_bottom_up = "--bottom-up" in argv
    show_both     = "--both"      in argv
    args = [a for a in argv[1:] if not a.startswith("--")]

    # -- Single expression or .expr file ---------------------
    if args:
        raw  = args[0]
        path = Path(raw)
        if path.exists() and path.suffix == ".expr":
            source      = path.read_text(encoding="utf-8")
            description = path.stem
        else:
            source      = raw
            description = "Input: " + raw

        if show_both:
            # Run with BOTH parsers so the report shows two tab sections
            cases = [
                ("[Top-Down]   " + description, source),
                ("[Bottom-Up]  " + description, source),
            ]
            for flag, lbl in [(False, "TOP-DOWN"), (True, "BOTTOM-UP")]:
                print()
                print("  -- " + lbl + " --")
                compile_source(source, use_bottom_up=flag)
            _save_report(cases, "Report for: " + repr(source) + "  (both parsers)")
        else:
            parser_label = "Bottom-Up" if use_bottom_up else "Top-Down"
            cases = [("[" + parser_label + "]  " + description, source)]
            compile_source(source, use_bottom_up=use_bottom_up)
            _save_report(cases, "Report for: " + repr(source) + "  (" + parser_label + " parser)")

        return 0

    # -- No arguments: full built-in test suite ---------------
    for parser_flag, lbl in [
        (False, "TOP-DOWN  (Recursive Descent, LL(1))"),
        (True,  "BOTTOM-UP (Shift-Reduce, operator-precedence)"),
    ]:
        print()
        print("*" * 64)
        print("  PARSER MODE: " + lbl)
        print("*" * 64)
        for description, source in TEST_CASES:
            print("\n  >> " + description)
            compile_source(source, use_bottom_up=parser_flag)

    _save_report(TEST_CASES, "Full test suite -- all cases, both parsers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
