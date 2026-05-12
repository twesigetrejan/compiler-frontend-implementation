# compiler/ast_nodes.py
# ─────────────────────────────────────────────────────────────
# AST node dataclasses and the tree pretty-printer.
#
# All nodes use frozen=True, slots=True  (integrated from the
# reference implementation) — nodes are immutable and memory-
# efficient, which is good practice for tree structures that are
# built once and then only read.
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════
# Base class
# ═══════════════════════════════════════════════════════════════

class ASTNode:
    """Marker base for every node in the Abstract Syntax Tree."""
    __slots__ = ()


# ═══════════════════════════════════════════════════════════════
# Concrete node types
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class Program(ASTNode):
    """Root node — holds every top-level statement."""
    statements: tuple[ASTNode, ...]


@dataclass(frozen=True, slots=True)
class Assign(ASTNode):
    """Variable assignment:  name = value"""
    name:  str
    value: ASTNode


@dataclass(frozen=True, slots=True)
class PrintStmt(ASTNode):
    """print(expr) statement — integrated from reference impl."""
    expression: ASTNode


@dataclass(frozen=True, slots=True)
class BinOp(ASTNode):
    """Binary arithmetic operation:  left  op  right"""
    left:  ASTNode
    op:    str        # '+' | '-' | '*' | '/'
    right: ASTNode


@dataclass(frozen=True, slots=True)
class Number(ASTNode):
    """Numeric literal — int or float."""
    value: int | float


@dataclass(frozen=True, slots=True)
class Identifier(ASTNode):
    """Variable reference."""
    name: str


# ═══════════════════════════════════════════════════════════════
# AST tree printer
# ═══════════════════════════════════════════════════════════════

def format_ast(node: ASTNode, prefix: str = "", is_last: bool = True) -> str:
    """
    Return a multi-line string that draws the AST as a branching tree,
    for example:

        Program
        └── Assign  →  'x'
              └── BinOp  [+]
                    ├── Number  3
                    └── BinOp  [*]
                          ├── Number  5
                          └── Number  2
    """
    connector  = "└── " if is_last else "├── "
    child_pfx  = prefix + ("      " if is_last else "│     ")
    lines: list[str] = []

    if isinstance(node, Program):
        lines.append("Program")
        for i, stmt in enumerate(node.statements):
            lines.append(format_ast(stmt, "", i == len(node.statements) - 1))

    elif isinstance(node, Assign):
        lines.append(f"{prefix}{connector}Assign  →  {node.name!r}")
        lines.append(format_ast(node.value, child_pfx, True))

    elif isinstance(node, PrintStmt):
        lines.append(f"{prefix}{connector}PrintStmt")
        lines.append(format_ast(node.expression, child_pfx, True))

    elif isinstance(node, BinOp):
        lines.append(f"{prefix}{connector}BinOp  [{node.op}]")
        lines.append(format_ast(node.left,  child_pfx, False))
        lines.append(format_ast(node.right, child_pfx, True))

    elif isinstance(node, Number):
        lines.append(f"{prefix}{connector}Number  {node.value}")

    elif isinstance(node, Identifier):
        lines.append(f"{prefix}{connector}Identifier  {node.name!r}")

    else:
        lines.append(f"{prefix}{connector}<unknown node: {type(node).__name__}>")

    return "\n".join(lines)
