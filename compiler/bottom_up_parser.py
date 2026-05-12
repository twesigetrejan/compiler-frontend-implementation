# compiler/bottom_up_parser.py
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program, format_ast,
)
from compiler.lexer import Lexer
from compiler.tokens import Token, TokenType

PRECEDENCE: dict[TokenType, int] = {
    TokenType.PLUS: 1, TokenType.MINUS: 1,
    TokenType.MULTIPLY: 2, TokenType.DIVIDE: 2,
}
_BINARY_OPS = set(PRECEDENCE)

@dataclass(slots=True)
class Symbol:
    kind:  str
    value: Any
    token: Token

class BottomUpParseError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.line = line
        self.column = column

class BottomUpParser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens  = tokens
        self.index   = 0
        self.stack: list[Symbol] = []
        self.steps: list[str] = []
        self._step_n = 0

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
        self.steps.append("Accept -- stack fully reduced")
        return Program(tuple(stmts))

    def _shift(self) -> None:
        tok = self.tokens[self.index]
        self._step_n += 1
        remaining = [t.value for t in self.tokens[self.index + 1:]
                     if t.type != TokenType.EOF]
        stack_summary = " | ".join(s.kind for s in self.stack) or "empty"
        self.steps.append(
            f"Step {self._step_n}:  SHIFT  {tok.type.name}('{tok.value}')"
            f"  |  stack: [{stack_summary}]"
            f"  |  remaining: {remaining or ['$']}"
        )
        self.stack.append(Symbol(tok.type.name, tok, tok))
        self.index += 1

    def _log_reduce(self, pattern: str, result: str) -> None:
        self._step_n += 1
        self.steps.append(f"Step {self._step_n}:  REDUCE  {pattern}  ->  {result}")

    def _reduce_all(self, lookahead: Token) -> None:
        while self._try_reduce(lookahead):
            pass

    def _try_reduce(self, lookahead: Token) -> bool:
        return (
            self._reduce_literal()
            or self._reduce_identifier(lookahead)
            or self._reduce_print()
            or self._reduce_parenthesised()
            or self._reduce_binary(lookahead)
            or self._reduce_assignment(lookahead)
            or self._reduce_trailing_semicolon()
            or self._reduce_expr_stmt(lookahead)
        )

    def _reduce_literal(self) -> bool:
        if not self._top_is("NUMBER"):
            return False
        sym = self.stack.pop()
        raw = sym.token.value
        val = float(raw) if "." in raw else int(raw)
        self.stack.append(Symbol("EXPR", Number(val), sym.token))
        self._log_reduce(f"NUMBER('{raw}')", f"EXPR({val})")
        return True

    def _reduce_identifier(self, lookahead: Token) -> bool:
        if not self._top_is("IDENTIFIER"):
            return False
        if lookahead.type == TokenType.ASSIGN:
            return False
        sym = self.stack.pop()
        self.stack.append(Symbol("EXPR", Identifier(sym.token.value), sym.token))
        self._log_reduce(f"IDENTIFIER('{sym.token.value}')", f"EXPR(id={sym.token.value})")
        return True

    def _reduce_print(self) -> bool:
        if self._suffix_is("PRINT", "LPAREN", "EXPR", "RPAREN", "SEMICOLON"):
            _sc, _rp, expr, _lp, kw = (self.stack.pop() for _ in range(5))
            self.stack.append(Symbol("STMT", PrintStmt(expr.value), kw.token))
            self._log_reduce("PRINT LPAREN EXPR RPAREN SEMICOLON", "STMT(print)")
            return True
        if self._suffix_is("PRINT", "LPAREN", "EXPR", "RPAREN"):
            _rp, expr, _lp, kw = (self.stack.pop() for _ in range(4))
            self.stack.append(Symbol("STMT", PrintStmt(expr.value), kw.token))
            self._log_reduce("PRINT LPAREN EXPR RPAREN", "STMT(print)")
            return True
        return False

    def _reduce_parenthesised(self) -> bool:
        if not self._suffix_is("LPAREN", "EXPR", "RPAREN"):
            return False
        if len(self.stack) >= 4 and self.stack[-4].kind == "PRINT":
            return False
        _rp, inner, _lp = self.stack.pop(), self.stack.pop(), self.stack.pop()
        self.stack.append(Symbol("EXPR", inner.value, _lp.token))
        self._log_reduce("LPAREN EXPR RPAREN", "EXPR  (grouped)")
        return True

    def _reduce_binary(self, lookahead: Token) -> bool:
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
        op_val = op_sym.token.value
        self.stack[-3:] = [Symbol(
            "EXPR",
            BinOp(left_sym.value, op_val, right_sym.value),
            left_sym.token,
        )]
        self._log_reduce(f"EXPR '{op_val}' EXPR", f"BinOp[{op_val}]")
        return True

    def _reduce_assignment(self, lookahead: Token) -> bool:
        if lookahead.type in _BINARY_OPS:
            return False
        if self._suffix_is("IDENTIFIER", "ASSIGN", "EXPR", "SEMICOLON"):
            _sc, expr, _eq, name = (self.stack.pop() for _ in range(4))
            self.stack.append(Symbol("STMT", Assign(name.token.value, expr.value), name.token))
            self._log_reduce(
                f"IDENTIFIER('{name.token.value}') ASSIGN EXPR SEMICOLON",
                f"STMT(assign {name.token.value})"
            )
            return True
        if self._suffix_is("IDENTIFIER", "ASSIGN", "EXPR"):
            expr, _eq, name = (self.stack.pop() for _ in range(3))
            self.stack.append(Symbol("STMT", Assign(name.token.value, expr.value), name.token))
            self._log_reduce(
                f"IDENTIFIER('{name.token.value}') ASSIGN EXPR",
                f"STMT(assign {name.token.value})"
            )
            return True
        return False

    def _reduce_trailing_semicolon(self) -> bool:
        if self._suffix_is("STMT", "SEMICOLON", "STMT"):
            top = self.stack.pop()
            self.stack.pop()
            self.stack.append(top)
            self._log_reduce("STMT SEMICOLON STMT", "STMT STMT  (semicolon discarded)")
            return True
        if self._suffix_is("STMT", "SEMICOLON"):
            self.stack.pop()
            self._log_reduce("STMT SEMICOLON", "STMT  (trailing semicolon discarded)")
            return True
        return False

    def _reduce_expr_stmt(self, lookahead: Token) -> bool:
        if self._suffix_is("EXPR", "SEMICOLON"):
            _sc, expr = self.stack.pop(), self.stack.pop()
            self.stack.append(Symbol("STMT", expr.value, expr.token))
            self._log_reduce("EXPR SEMICOLON", "STMT")
            return True
        if self._top_is("EXPR") and lookahead.type == TokenType.EOF:
            expr = self.stack.pop()
            self.stack.append(Symbol("STMT", expr.value, expr.token))
            self._log_reduce("EXPR  (at EOF)", "STMT")
            return True
        return False

    def _should_reduce(self, stack_op: TokenType, lookahead_op: TokenType) -> bool:
        return PRECEDENCE.get(stack_op, 0) >= PRECEDENCE.get(lookahead_op, 0)

    def _top_is(self, kind: str) -> bool:
        return bool(self.stack) and self.stack[-1].kind == kind

    def _suffix_is(self, *kinds) -> bool:
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
