# compiler/bottom_up_parser.py
# ─────────────────────────────────────────────────────────────
# Phase 2 — Syntax Analysis  (Bottom-Up / Shift-Reduce Parser)
#
# Parser type  : Shift-Reduce, operator-precedence driven
# Strategy     : Bottom-up — reads tokens left to right, builds
#                the AST leaves-first, root last.
# Conflict res.: PRECEDENCE table decides shift vs. reduce when
#                two operators compete.
#
# Integrated and adapted from the reference implementation:
#   • PRECEDENCE table encoding
#   • Symbol / stack model
#   • _shift / _reduce_all / _try_reduce pattern
#   • _should_reduce_binary using precedence comparison
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program, UnaryOp,
    format_ast,
)
from compiler.lexer import Lexer
from compiler.tokens import Token, TokenType


# ── Precedence table (from reference implementation) ──────────
PRECEDENCE: dict[TokenType, int] = {
    TokenType.PLUS:     1,
    TokenType.MINUS:    1,
    TokenType.MULTIPLY: 2,
    TokenType.DIVIDE:   2,
}
_BINARY_OPS = set(PRECEDENCE)


# ── Stack symbol ───────────────────────────────────────────────
@dataclass(slots=True)
class Symbol:
    kind:  str
    value: Any
    token: Token


# ── Error ──────────────────────────────────────────────────────
class BottomUpParseError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.line   = line
        self.column = column


# ══════════════════════════════════════════════════════════════
# Parser
# ══════════════════════════════════════════════════════════════

class BottomUpParser:
    """
    Operator-precedence shift-reduce parser.
    Produces the same AST as the top-down recursive descent parser
    but builds the tree from leaves up to the root.
    """

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index  = 0
        self.stack: list[Symbol] = []

    # ── Public API ─────────────────────────────────────────

    def parse(self) -> Program:
        while not self._at_end():
            self._shift()
            self._reduce_all(self._lookahead())

        self._reduce_all(self._eof_token())

        stmts: list[ASTNode] = []
        for sym in self.stack:
            if sym.kind in ("STMT", "EXPR"):
                stmts.append(sym.value)
            else:
                tok = sym.token
                raise BottomUpParseError(
                    f"[Parser Error] Could not reduce {sym.kind!r} "
                    f"near {tok.value!r} at line {tok.line}, column {tok.column}",
                    tok.line, tok.column,
                )
        return Program(tuple(stmts))

    # ── Shift ──────────────────────────────────────────────

    def _shift(self) -> None:
        tok = self.tokens[self.index]
        self.stack.append(Symbol(tok.type.name, tok, tok))
        self.index += 1

    # ── Reduce loop ────────────────────────────────────────

    def _reduce_all(self, lookahead: Token) -> None:
        while self._try_reduce(lookahead):
            pass

    def _try_reduce(self, lookahead: Token) -> bool:
        # ORDER MATTERS:
        #   _reduce_print must come before _reduce_parenthesised so that
        #   PRINT LPAREN EXPR RPAREN → STMT fires before the inner
        #   LPAREN EXPR RPAREN → EXPR rule can swallow the parentheses.
        #   _reduce_trailing_semicolon cleans up lone ';' between statements.
        return (
            self._reduce_literal()
            or self._reduce_identifier(lookahead)
            or self._reduce_unary()
            or self._reduce_print()
            or self._reduce_parenthesised()
            or self._reduce_binary(lookahead)
            or self._reduce_assignment(lookahead)
            or self._reduce_trailing_semicolon()
            or self._reduce_expr_stmt(lookahead)
        )

    # ── Reduction rules ────────────────────────────────────

    def _reduce_literal(self) -> bool:
        """NUMBER → EXPR"""
        if not self._top_is("NUMBER"):
            return False
        sym = self.stack.pop()
        raw = sym.token.value
        val = float(raw) if "." in raw else int(raw)
        self.stack.append(Symbol("EXPR", Number(val), sym.token))
        return True

    def _reduce_unary(self) -> bool:
        """(MINUS | PLUS) EXPR → EXPR  [unary negation or positive]"""
        if len(self.stack) < 2:
            return False
        right_sym = self.stack[-1]
        op_sym    = self.stack[-2]

        if right_sym.kind != "EXPR":
            return False
        if op_sym.token.type not in (TokenType.MINUS, TokenType.PLUS):
            return False

        self.stack[-2:] = [Symbol(
            "EXPR",
            UnaryOp(op_sym.token.value, right_sym.value),
            op_sym.token,
        )]
        return True

    def _reduce_identifier(self, lookahead: Token) -> bool:
        """IDENTIFIER → EXPR  (skip when lookahead is '=': LHS of assignment)"""
        if not self._top_is("IDENTIFIER"):
            return False
        if lookahead.type == TokenType.ASSIGN:
            return False
        sym = self.stack.pop()
        self.stack.append(Symbol("EXPR", Identifier(sym.token.value), sym.token))
        return True

    def _reduce_print(self) -> bool:
        """
        PRINT LPAREN EXPR RPAREN → STMT
        Must be checked BEFORE _reduce_parenthesised so the full
        print-call pattern wins over the generic grouping rule.
        """
        if self._suffix_is("PRINT", "LPAREN", "EXPR", "RPAREN", "SEMICOLON"):
            _sc, _rp, expr, _lp, kw = (self.stack.pop() for _ in range(5))
            self.stack.append(Symbol("STMT", PrintStmt(expr.value), kw.token))
            return True
        if self._suffix_is("PRINT", "LPAREN", "EXPR", "RPAREN"):
            _rp, expr, _lp, kw = (self.stack.pop() for _ in range(4))
            self.stack.append(Symbol("STMT", PrintStmt(expr.value), kw.token))
            return True
        return False

    def _reduce_parenthesised(self) -> bool:
        """
        LPAREN EXPR RPAREN → EXPR
        Also handles: LPAREN (MINUS|PLUS) EXPR RPAREN → EXPR (unary inside parens)
        Guard: skip if the item before LPAREN is PRINT — that case
        belongs to _reduce_print (same guard as reference implementation).
        """
        # First try: LPAREN (MINUS|PLUS) EXPR RPAREN → EXPR with unary
        if (self._suffix_is("LPAREN", None, "EXPR", "RPAREN") and
            len(self.stack) >= 4 and
            self.stack[-4].kind == "LPAREN" and
            self.stack[-3].token.type in (TokenType.MINUS, TokenType.PLUS)):
            # Don't fire inside a print() call
            if len(self.stack) >= 5 and self.stack[-5].kind == "PRINT":
                return False
            _rp, expr, op, _lp = self.stack.pop(), self.stack.pop(), self.stack.pop(), self.stack.pop()
            unary_node = UnaryOp(op.token.value, expr.value)
            self.stack.append(Symbol("EXPR", unary_node, _lp.token))
            return True
        
        # Standard case: LPAREN EXPR RPAREN → EXPR
        if not self._suffix_is("LPAREN", "EXPR", "RPAREN"):
            return False
        # Don't fire inside a print() call
        if len(self.stack) >= 4 and self.stack[-4].kind == "PRINT":
            return False
        _rp, inner, _lp = self.stack.pop(), self.stack.pop(), self.stack.pop()
        self.stack.append(Symbol("EXPR", inner.value, _lp.token))
        return True

    def _reduce_binary(self, lookahead: Token) -> bool:
        """
        EXPR op EXPR → EXPR
        Reduce only when the stack operator's precedence >= lookahead's,
        implementing left-associativity and correct binding order.
        (Logic from reference implementation's _should_reduce_binary.)
        """
        if len(self.stack) < 3:
            return False
        right_sym = self.stack[-1]
        op_sym    = self.stack[-2]
        left_sym  = self.stack[-3]

        if left_sym.kind != "EXPR" or right_sym.kind != "EXPR":
            return False
        op_type = op_sym.token.type
        if op_type not in _BINARY_OPS:
            return False
        if not self._should_reduce(op_type, lookahead.type):
            return False

        self.stack[-3:] = [Symbol(
            "EXPR",
            BinOp(left_sym.value, op_sym.token.value, right_sym.value),
            left_sym.token,
        )]
        return True

    def _reduce_assignment(self, lookahead: Token) -> bool:
        """IDENTIFIER ASSIGN EXPR (SEMICOLON?) → STMT"""
        if lookahead.type in _BINARY_OPS:
            return False
        if self._suffix_is("IDENTIFIER", "ASSIGN", "EXPR", "SEMICOLON"):
            _sc, expr, _eq, name = (self.stack.pop() for _ in range(4))
            self.stack.append(Symbol("STMT", Assign(name.token.value, expr.value), name.token))
            return True
        if self._suffix_is("IDENTIFIER", "ASSIGN", "EXPR"):
            expr, _eq, name = (self.stack.pop() for _ in range(3))
            self.stack.append(Symbol("STMT", Assign(name.token.value, expr.value), name.token))
            return True
        return False

    def _reduce_trailing_semicolon(self) -> bool:
        """
        STMT SEMICOLON → STMT  (or just discard a lone SEMICOLON after a statement)
        Handles the case where a semicolon separates two statements and has
        already been shifted on top of the first STMT before the second
        statement is shifted on top of it.

        Also handles STMT SEMICOLON STMT → discard the middle SEMICOLON,
        which occurs when the second statement was reduced before this rule
        fired.
        """
        # [STMT, SEMICOLON, STMT] → drop the SEMICOLON
        if self._suffix_is("STMT", "SEMICOLON", "STMT"):
            top  = self.stack.pop()          # pop second STMT
            self.stack.pop()                 # pop SEMICOLON
            self.stack.append(top)           # push second STMT back
            return True
        # [STMT, SEMICOLON] → drop the SEMICOLON
        if self._suffix_is("STMT", "SEMICOLON"):
            self.stack.pop()                 # pop SEMICOLON, STMT stays
            return True
        return False

    def _reduce_expr_stmt(self, lookahead: Token) -> bool:
        """EXPR (';'?) → STMT  — only at end of input or after explicit ';'"""
        if self._suffix_is("EXPR", "SEMICOLON"):
            _sc, expr = self.stack.pop(), self.stack.pop()
            self.stack.append(Symbol("STMT", expr.value, expr.token))
            return True
        if self._top_is("EXPR") and lookahead.type == TokenType.EOF:
            expr = self.stack.pop()
            self.stack.append(Symbol("STMT", expr.value, expr.token))
            return True
        return False

    # ── Shift-reduce decision ──────────────────────────────

    def _should_reduce(self, stack_op: TokenType, lookahead_op: TokenType) -> bool:
        """Reduce if stack operator precedence >= lookahead (left-associativity)."""
        return PRECEDENCE.get(stack_op, 0) >= PRECEDENCE.get(lookahead_op, 0)

    # ── Stack helpers ──────────────────────────────────────

    def _top_is(self, kind: str) -> bool:
        return bool(self.stack) and self.stack[-1].kind == kind

    def _suffix_is(self, *kinds: str | None) -> bool:
        n = len(kinds)
        if len(self.stack) < n:
            return False
        for expected, sym in zip(kinds, self.stack[-n:]):
            if expected is not None and sym.kind != expected:
                return False
        return True

    def _lookahead(self) -> Token:
        return self.tokens[self.index] if not self._at_end() else self._eof_token()

    def _eof_token(self) -> Token:
        return self.tokens[-1]

    def _at_end(self) -> bool:
        return (
            self.index >= len(self.tokens)
            or self.tokens[self.index].type == TokenType.EOF
        )


# ── Helpers ────────────────────────────────────────────────────

def parse_tokens_bottom_up(tokens: list[Token]) -> Program:
    return BottomUpParser(tokens).parse()


def parse_source_bottom_up(source: str) -> tuple[Program, list]:
    tokens, lex_errors = Lexer(source).tokenize()
    return BottomUpParser(tokens).parse(), lex_errors


def main(argv: list[str]) -> int:
    path   = Path(argv[1]) if len(argv) > 1 else Path("examples/sample.expr")
    source = path.read_text(encoding="utf-8")
    program, _ = parse_source_bottom_up(source)
    print(format_ast(program))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
