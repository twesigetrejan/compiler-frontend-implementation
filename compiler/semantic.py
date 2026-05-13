# compiler/semantic.py
# ─────────────────────────────────────────────────────────────
# Phase 3 — Semantic Analysis
#
# The semantic analyser walks the AST produced by either parser,
# enforces the language's semantic rules, and evaluates
# expressions to concrete values.
#
# Integrations from reference implementation:
#   • Scoped symbol table with push_scope / pop_scope — variables
#     declared inside a nested block shadow outer ones but do not
#     pollute the outer scope when the block exits.
#   • _resolve() walks scopes from innermost outward (same pattern
#     as reference implementation's reversed-scope lookup).
#   • SemanticError carries a descriptive message including the
#     variable name or operator involved.
#
# Checks performed
# ────────────────
#   1. Undefined variable — identifier used before assignment
#   2. Division by zero   — divisor evaluates to 0
#   3. Type consistency   — operands of arithmetic must be numeric
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program,
)
from compiler.lexer import Lexer
from compiler.parser import Parser


# ═══════════════════════════════════════════════════════════════
# Error type
# ═══════════════════════════════════════════════════════════════

class SemanticError(ValueError):
    """Raised when the AST violates a semantic rule."""
    def __init__(self, message: str, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line   = line
        self.column = column


# ═══════════════════════════════════════════════════════════════
# Semantic Analyser
# ═══════════════════════════════════════════════════════════════

class SemanticAnalyzer:
    """
    Walks the AST, checks semantic rules, and evaluates each
    expression to a numeric value.

    The scoped symbol table (list of dicts) is adopted from the
    reference implementation: the innermost scope is always at
    index -1.  push_scope() / pop_scope() manage block boundaries.
    """

    def __init__(self) -> None:
        # Start with one global scope
        self.scopes: list[dict[str, int | float]] = [{}]

    # ── Scope management (from reference implementation) ───

    def push_scope(self) -> None:
        self.scopes.append({})

    def pop_scope(self) -> None:
        if len(self.scopes) > 1:
            self.scopes.pop()

    def _declare(self, name: str, value: int | float) -> None:
        """Store a name in the current (innermost) scope."""
        self.scopes[-1][name] = value

    def _resolve(self, name: str, line: int | None = None, column: int | None = None) -> int | float:
        """
        Walk scopes from innermost outward — same search order as
        the reference implementation — and return the value if found.
        Raises SemanticError if the name is undeclared in all scopes.
        """
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise SemanticError(
            f"[Semantic Error] Undefined variable '{name}'",
            line, column
        )

    @property
    def symbol_table(self) -> dict[str, int | float]:
        """Flat view of the global (outermost) scope — used by tests and pipeline."""
        return self.scopes[0]

    # ── Main analysis entry point ──────────────────────────

    def analyze(self, node: ASTNode) -> Any:
        """
        Recursively analyse and evaluate `node`.
        Returns a numeric value for expressions, None for statements
        that produce no value (print), or a list for Program.
        """

        if isinstance(node, Program):
            return [self.analyze(stmt) for stmt in node.statements]

        if isinstance(node, Assign):
            value = self.analyze(node.value)
            self._declare(node.name, value)
            return value

        if isinstance(node, PrintStmt):
            value = self.analyze(node.expression)
            print(f"  [print] {value}")
            return None

        if isinstance(node, BinOp):
            left  = self.analyze(node.left)
            right = self.analyze(node.right)

            # Type check
            if not isinstance(left, (int, float)):
                raise SemanticError(
                    f"[Semantic Error] Left operand of '{node.op}' "
                    f"is not numeric: {left!r}",
                    node.line, node.column
                )
            if not isinstance(right, (int, float)):
                raise SemanticError(
                    f"[Semantic Error] Right operand of '{node.op}' "
                    f"is not numeric: {right!r}",
                    node.line, node.column
                )

            # Division by zero
            if node.op == "/" and right == 0:
                raise SemanticError(
                    "[Semantic Error] Division by zero",
                    node.line, node.column
                )

            return {
                "+": lambda a, b: a + b,
                "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
                "/": lambda a, b: a / b,
            }[node.op](left, right)

        if isinstance(node, Number):
            return node.value

        if isinstance(node, Identifier):
            return self._resolve(node.name, node.line, node.column)

        raise SemanticError(
            f"[Semantic Error] Unknown AST node type: {type(node).__name__!r}"
        )


# ═══════════════════════════════════════════════════════════════
# Convenience helpers
# ═══════════════════════════════════════════════════════════════

def analyze_source(source: str) -> tuple[list[Any], dict[str, Any]]:
    tokens, _ = Lexer(source).tokenize()
    ast       = Parser(tokens).parse()
    analyzer  = SemanticAnalyzer()
    results   = analyzer.analyze(ast)
    return results, analyzer.symbol_table


# ═══════════════════════════════════════════════════════════════
# Stand-alone entry point
# ═══════════════════════════════════════════════════════════════

def main(argv: list[str]) -> int:
    path   = Path(argv[1]) if len(argv) > 1 else Path("examples/sample.expr")
    source = path.read_text(encoding="utf-8")
    results, table = analyze_source(source)
    print("Symbol table:")
    for name, val in table.items():
        print(f"  {name} = {val}")
    print("\nResults:", [r for r in results if r is not None])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
