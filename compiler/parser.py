# compiler/parser.py
# ─────────────────────────────────────────────────────────────
# Phase 2 — Syntax Analysis  (Top-Down Parser)
#
# Parser type : Recursive Descent, LL(1), top-down, predictive
# Look-ahead  : 1 token
# Associativity: Left-to-right for all binary operators
#
# The grammar is written so that precedence is encoded in the
# call hierarchy — lower-precedence rules call higher-precedence
# ones, so higher-precedence operators bind tighter naturally.
#
# Grammar
# ───────
#   program    →  statement* EOF
#   statement  →  assignment
#              |  print_stmt
#              |  expr (';')?
#   assignment →  IDENTIFIER '=' expr (';')?
#   print_stmt →  PRINT '(' expr ')' (';')?
#   expr       →  term ( ('+' | '-') term )*       ← lowest precedence
#   term       →  factor ( ('*' | '/') factor )*   ← medium precedence
#   factor     →  NUMBER                            ← highest / atoms
#              |  IDENTIFIER
#              |  '(' expr ')'
#
# Each grammar rule is one method; reading the methods in order
# IS reading the grammar.
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program,
    format_ast,
)
from compiler.lexer import Lexer
from compiler.tokens import Token, TokenType


# ═══════════════════════════════════════════════════════════════
# Error type
# ═══════════════════════════════════════════════════════════════

class ParseError(ValueError):
    """Raised when the token stream does not conform to the grammar."""
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.line   = line
        self.column = column


# ═══════════════════════════════════════════════════════════════
# Parser
# ═══════════════════════════════════════════════════════════════

class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos    = 0
        self.steps: list[str] = []   # ← step-by-step parse trace

    # ── Navigation helpers ─────────────────────────────────

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _consume(self, expected: TokenType, message: str) -> Token:
        if self._current().type == expected:
            return self._advance()
        tok = self._current()
        raise ParseError(
            f"[Parser Error] {message} — "
            f"found {tok.type.name} ({tok.value!r}) "
            f"at line {tok.line}, column {tok.column}",
            tok.line, tok.column,
        )

    # ── Trace helper ───────────────────────────────────────

    def _trace(self, msg: str) -> None:
        tok = self._current()
        self.steps.append(f"{msg}  [token: {tok.type.name}({tok.value!r})]")

    # ── Grammar rules (one method per rule) ───────────────

    def parse(self) -> Program:
        """program → statement* EOF"""
        stmts: list[ASTNode] = []
        step = 1
        while not self._check(TokenType.EOF):
            self.steps.append(f"── Statement {step} ──")
            stmts.append(self._statement())
            step += 1
        self._consume(TokenType.EOF, "Expected end of input")
        self.steps.append("✓  Accept — input fully consumed")
        return Program(tuple(stmts))

    def _statement(self) -> ASTNode:
        """
        statement → assignment | print_stmt | expr (';')?

        One token of look-ahead disambiguates:
          IDENTIFIER followed by '='  → assignment
          PRINT                       → print_stmt
          anything else               → expression statement
        """
        if (self._check(TokenType.IDENTIFIER)
                and self._peek().type == TokenType.ASSIGN):
            self._trace("Predict  stmt → id '=' expr ';'")
            return self._assignment()

        if self._check(TokenType.PRINT):
            self._trace("Predict  stmt → print '(' expr ')' ';'")
            return self._print_stmt()

        self._trace("Predict  stmt → expr ';'")
        node = self._expr()
        self._match(TokenType.SEMICOLON)
        return node

    def _assignment(self) -> Assign:
        """assignment → IDENTIFIER '=' expr (';')?"""
        name_tok = self._advance()          # consume IDENTIFIER
        self.steps.append(f"  Match  id → '{name_tok.value}'")
        self._advance()                     # consume '='
        self.steps.append("  Match  '='")
        self._trace("  Apply  expr →")
        value    = self._expr()
        self._match(TokenType.SEMICOLON)
        self.steps.append(f"  Assign '{name_tok.value}' = <expr>  ✓")
        return Assign(name_tok.value, value)

    def _print_stmt(self) -> PrintStmt:
        """print_stmt → PRINT '(' expr ')' (';')?"""
        self._advance()                                         # consume 'print'
        self.steps.append("  Match  'print'")
        self._consume(TokenType.LPAREN, "Expected '(' after 'print'")
        self.steps.append("  Match  '('")
        self._trace("  Apply  expr →")
        expr = self._expr()
        self._consume(TokenType.RPAREN, "Expected ')' after print expression")
        self.steps.append("  Match  ')'")
        self._match(TokenType.SEMICOLON)
        self.steps.append("  PrintStmt built  ✓")
        return PrintStmt(expr)

    def _expr(self) -> ASTNode:
        """expr → term ( ('+' | '-') term )*   [lowest precedence]"""
        self._trace("  Apply  expr → term expr'")
        node = self._term()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op    = self._advance().value            # '+' or '-'
            self.steps.append(f"  expr': Match op '{op}'  → expr' → '{op}' term expr'")
            right = self._term()
            node  = BinOp(node, op, right)           # left-associative
            self.steps.append(f"  Reduce  EXPR '{op}' EXPR  →  BinOp[{op}]")
        self.steps.append("  expr' → ε  (no more + or -)")
        return node

    def _term(self) -> ASTNode:
        """term → factor ( ('*' | '/') factor )*   [medium precedence]"""
        self._trace("  Apply  term → factor term'")
        node = self._factor()
        while self._check(TokenType.MULTIPLY, TokenType.DIVIDE):
            op    = self._advance().value            # '*' or '/'
            self.steps.append(f"  term': Match op '{op}'  → term' → '{op}' factor term'")
            right = self._factor()
            node  = BinOp(node, op, right)           # left-associative
            self.steps.append(f"  Reduce  EXPR '{op}' EXPR  →  BinOp[{op}]")
        self.steps.append("  term' → ε  (no more * or /)")
        return node

    def _factor(self) -> ASTNode:
        """factor → NUMBER | IDENTIFIER | '(' expr ')'   [highest / atoms]"""
        tok = self._current()

        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value) if "." in tok.value else int(tok.value)
            self.steps.append(f"  factor → num  Match '{tok.value}'")
            return Number(val)

        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            self.steps.append(f"  factor → id   Match '{tok.value}'")
            return Identifier(tok.value)

        if tok.type == TokenType.LPAREN:
            self._advance()                 # consume '('
            self.steps.append("  factor → '(' expr ')'  Match '('")
            node = self._expr()
            self._consume(TokenType.RPAREN, "Expected ')' after expression")
            self.steps.append("  Match ')'")
            return node

        raise ParseError(
            f"[Parser Error] Unexpected token {tok.type.name} ({tok.value!r}) "
            f"at line {tok.line}, column {tok.column}",
            tok.line, tok.column,
        )


# ═══════════════════════════════════════════════════════════════
# Convenience helpers used by tests and pipeline
# ═══════════════════════════════════════════════════════════════

def parse_tokens(tokens: list[Token]) -> Program:
    return Parser(tokens).parse()


def parse_source(source: str) -> tuple[Program, list]:
    tokens, lex_errors = Lexer(source).tokenize()
    return Parser(tokens).parse(), lex_errors


# ═══════════════════════════════════════════════════════════════
# Stand-alone entry point
# ═══════════════════════════════════════════════════════════════

def main(argv: list[str]) -> int:
    path   = Path(argv[1]) if len(argv) > 1 else Path("examples/sample.expr")
    source = path.read_text(encoding="utf-8")
    program, _ = parse_source(source)
    print(format_ast(program))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
