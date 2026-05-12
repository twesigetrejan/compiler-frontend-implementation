# tests/test_parser.py
# ─────────────────────────────────────────────────────────────
# Unit tests for Phase 2 — Syntax Analysis
# Covers both the top-down (recursive descent) parser and the
# bottom-up (shift-reduce) parser.
# ─────────────────────────────────────────────────────────────

import unittest
from compiler.lexer import Lexer
from compiler.parser import Parser, ParseError
from compiler.bottom_up_parser import BottomUpParser, BottomUpParseError
from compiler.ast_nodes import Assign, BinOp, Identifier, Number, PrintStmt, Program


def _parse_td(source: str) -> Program:
    """Top-down (recursive descent) parse."""
    tokens, _ = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _parse_bu(source: str) -> Program:
    """Bottom-up (shift-reduce) parse."""
    tokens, _ = Lexer(source).tokenize()
    return BottomUpParser(tokens).parse()


class TestPrecedence(unittest.TestCase):
    """Both parsers must encode operator precedence identically."""

    def _check_both(self, source: str, check_fn):
        check_fn(self, _parse_td(source))
        check_fn(self, _parse_bu(source))

    def test_multiply_binds_tighter_than_add(self):
        # 3 + 5 * 2  →  root='+', right child='*'
        def check(t, tree):
            root = tree.statements[0]
            t.assertIsInstance(root, BinOp)
            t.assertEqual(root.op, "+")
            t.assertIsInstance(root.right, BinOp)
            t.assertEqual(root.right.op, "*")
        self._check_both("3 + 5 * 2", check)

    def test_parentheses_override_precedence(self):
        # (2 + 3) * 4  →  root='*', left child='+'
        def check(t, tree):
            root = tree.statements[0]
            t.assertEqual(root.op, "*")
            t.assertIsInstance(root.left, BinOp)
            t.assertEqual(root.left.op, "+")
        self._check_both("(2 + 3) * 4", check)

    def test_left_associativity_subtraction(self):
        # 10 - 4 - 2  →  BinOp(BinOp(10,'-',4), '-', 2)
        def check(t, tree):
            root = tree.statements[0]
            t.assertEqual(root.op, "-")
            t.assertIsInstance(root.left, BinOp)
            t.assertEqual(root.left.op, "-")
            # left subtree: 10 - 4
            t.assertEqual(root.left.left.value, 10)
            t.assertEqual(root.left.right.value, 4)
            # right: 2
            t.assertEqual(root.right.value, 2)
        self._check_both("10 - 4 - 2", check)

    def test_left_associativity_division(self):
        # 12 / 4 / 3  →  BinOp(BinOp(12,'/',4), '/', 3)  = 1
        def check(t, tree):
            root = tree.statements[0]
            t.assertEqual(root.op, "/")
            t.assertIsInstance(root.left, BinOp)
        self._check_both("12 / 4 / 3", check)


class TestASTStructure(unittest.TestCase):
    """Verify correct AST node types are produced."""

    def test_number_literal(self):
        tree = _parse_td("42")
        self.assertIsInstance(tree.statements[0], Number)
        self.assertEqual(tree.statements[0].value, 42)

    def test_float_literal(self):
        tree = _parse_td("3.14")
        self.assertAlmostEqual(tree.statements[0].value, 3.14)

    def test_identifier_node(self):
        tree = _parse_td("x")
        self.assertIsInstance(tree.statements[0], Identifier)
        self.assertEqual(tree.statements[0].name, "x")

    def test_assignment_node(self):
        tree = _parse_td("x = 10")
        node = tree.statements[0]
        self.assertIsInstance(node, Assign)
        self.assertEqual(node.name, "x")
        self.assertIsInstance(node.value, Number)
        self.assertEqual(node.value.value, 10)

    def test_print_statement_node(self):
        tree = _parse_td("print(42)")
        node = tree.statements[0]
        self.assertIsInstance(node, PrintStmt)
        self.assertIsInstance(node.expression, Number)

    def test_multiple_statements(self):
        tree = _parse_td("x = 1; y = 2")
        self.assertEqual(len(tree.statements), 2)
        self.assertIsInstance(tree.statements[0], Assign)
        self.assertIsInstance(tree.statements[1], Assign)

    def test_program_is_root_node(self):
        tree = _parse_td("1 + 2")
        self.assertIsInstance(tree, Program)


class TestTopDownErrors(unittest.TestCase):
    """Syntax errors caught by the recursive descent parser."""

    def test_consecutive_operators(self):
        with self.assertRaises(ParseError):
            _parse_td("3 + * 2")

    def test_unclosed_parenthesis(self):
        with self.assertRaises(ParseError):
            _parse_td("(3 + 5")

    def test_empty_parentheses(self):
        with self.assertRaises(ParseError):
            _parse_td("()")

    def test_trailing_operator(self):
        with self.assertRaises(ParseError):
            _parse_td("3 +")

    def test_missing_print_paren(self):
        with self.assertRaises(ParseError):
            _parse_td("print 42")


class TestBottomUpMatchesTopDown(unittest.TestCase):
    """
    The two parsers must produce structurally identical ASTs for
    all valid inputs.
    """

    def _assert_same_ast(self, source: str):
        td = _parse_td(source)
        bu = _parse_bu(source)
        self.assertEqual(td, bu, f"AST mismatch for: {source!r}")

    def test_simple_number(self):
        self._assert_same_ast("42")

    def test_addition(self):
        self._assert_same_ast("1 + 2")

    def test_precedence(self):
        self._assert_same_ast("3 + 5 * 2")

    def test_parentheses(self):
        self._assert_same_ast("(2 + 3) * 4")

    def test_left_assoc_subtraction(self):
        self._assert_same_ast("10 - 4 - 2")

    def test_assignment(self):
        self._assert_same_ast("x = 10")

    def test_multi_statement(self):
        self._assert_same_ast("x = 1; y = 2")

    def test_print_statement(self):
        self._assert_same_ast("print(42)")


if __name__ == "__main__":
    unittest.main()
