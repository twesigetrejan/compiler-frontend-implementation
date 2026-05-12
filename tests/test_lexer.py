# tests/test_lexer.py
# ─────────────────────────────────────────────────────────────
# Unit tests for Phase 1 — Lexical Analysis
# ─────────────────────────────────────────────────────────────

import unittest
from compiler.lexer import Lexer, LexerError
from compiler.tokens import TokenType


def _tokenize(source: str) -> list:
    tokens, errors = Lexer(source).tokenize()
    if errors:
        raise errors[0]
    return tokens


def _types(source: str) -> list[TokenType]:
    return [t.type for t in _tokenize(source)]


def _errors(source: str) -> list[LexerError]:
    _, errors = Lexer(source).tokenize()
    return errors


class TestRE1Numbers(unittest.TestCase):
    """RE1 = r'(?P<NUMBER>\d+(?:\.\d+)?)'"""

    def test_integer_literal(self):
        toks = _tokenize("42")
        self.assertEqual(toks[0].type, TokenType.NUMBER)
        self.assertEqual(toks[0].value, "42")

    def test_float_literal(self):
        toks = _tokenize("3.14")
        self.assertEqual(toks[0].type, TokenType.NUMBER)
        self.assertEqual(toks[0].value, "3.14")

    def test_zero(self):
        self.assertEqual(_types("0"), [TokenType.NUMBER, TokenType.EOF])

    def test_float_starting_with_zero(self):
        toks = _tokenize("0.5")
        self.assertEqual(toks[0].value, "0.5")


class TestRE2Identifiers(unittest.TestCase):
    """RE2 = r'(?P<IDENTIFIER>[a-zA-Z_][a-zA-Z0-9_]*)'"""

    def test_single_letter(self):
        self.assertEqual(_types("x"), [TokenType.IDENTIFIER, TokenType.EOF])

    def test_multichar_identifier(self):
        toks = _tokenize("result")
        self.assertEqual(toks[0].type, TokenType.IDENTIFIER)
        self.assertEqual(toks[0].value, "result")

    def test_underscore_prefix(self):
        toks = _tokenize("_tmp")
        self.assertEqual(toks[0].type, TokenType.IDENTIFIER)

    def test_identifier_with_digits(self):
        toks = _tokenize("var1")
        self.assertEqual(toks[0].type, TokenType.IDENTIFIER)

    def test_keyword_print_reclassified(self):
        # 'print' is matched by RE2 then reclassified via KEYWORDS dict
        self.assertEqual(_types("print"), [TokenType.PRINT, TokenType.EOF])


class TestRE3Operators(unittest.TestCase):
    """RE3 = r'(?P<OPERATOR>[+\\-*/()=;])'"""

    def test_all_single_operators(self):
        types = _types("+ - * / ( ) = ;")
        expected = [
            TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY,
            TokenType.DIVIDE, TokenType.LPAREN, TokenType.RPAREN,
            TokenType.ASSIGN, TokenType.SEMICOLON, TokenType.EOF,
        ]
        self.assertEqual(types, expected)


class TestCombinedPattern(unittest.TestCase):
    """Tests for the master RE1 | RE2 | RE3 pattern."""

    def test_arithmetic_expression(self):
        self.assertEqual(
            _types("x + 1"),
            [TokenType.IDENTIFIER, TokenType.PLUS, TokenType.NUMBER, TokenType.EOF],
        )

    def test_assignment_statement(self):
        self.assertEqual(
            _types("x = 10"),
            [TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER, TokenType.EOF],
        )

    def test_whitespace_skipped(self):
        self.assertEqual(_types("  1   +   2  "), _types("1+2"))

    def test_comment_stripped(self):
        # '//' comment should produce no tokens for that line
        toks = _tokenize("1 + 2 // this is a comment")
        types = [t.type for t in toks]
        self.assertNotIn(TokenType.DIVIDE, types)
        self.assertEqual(types, [TokenType.NUMBER, TokenType.PLUS, TokenType.NUMBER, TokenType.EOF])

    def test_multiline_line_tracking(self):
        toks = _tokenize("x\ny")
        self.assertEqual(toks[0].line, 1)
        self.assertEqual(toks[1].line, 2)

    def test_column_tracking(self):
        toks = _tokenize("ab + 1")
        self.assertEqual(toks[0].column, 1)   # 'ab'
        self.assertEqual(toks[1].column, 4)   # '+'
        self.assertEqual(toks[2].column, 6)   # '1'

    def test_multiple_statements(self):
        types = _types("x = 1; y = 2")
        self.assertIn(TokenType.SEMICOLON, types)
        self.assertEqual(types.count(TokenType.ASSIGN), 2)


class TestLexerErrors(unittest.TestCase):

    def test_single_invalid_character(self):
        errs = _errors("3 + @ 2")
        self.assertEqual(len(errs), 1)
        self.assertIn("@", str(errs[0]))

    def test_multiple_invalid_characters_all_collected(self):
        # All invalid chars must be reported, not just the first
        errs = _errors("@ # $")
        self.assertEqual(len(errs), 3)

    def test_invalid_character_does_not_stop_valid_tokens(self):
        tokens, errs = Lexer("3 + @ 2").tokenize()
        self.assertEqual(len(errs), 1)
        # Valid tokens should still be produced
        types = [t.type for t in tokens]
        self.assertIn(TokenType.NUMBER, types)
        self.assertIn(TokenType.PLUS, types)

    def test_error_carries_line_and_column(self):
        errs = _errors("x + @")
        self.assertEqual(errs[0].line, 1)
        self.assertEqual(errs[0].column, 5)


if __name__ == "__main__":
    unittest.main()
