# tests/test_semantic.py
# ─────────────────────────────────────────────────────────────
# Unit tests for Phase 3 — Semantic Analysis
# ─────────────────────────────────────────────────────────────

import unittest
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer, SemanticError


def _analyze(source: str):
    tokens, _ = Lexer(source).tokenize()
    ast       = Parser(tokens).parse()
    analyzer  = SemanticAnalyzer()
    results   = analyzer.analyze(ast)
    return results, analyzer.symbol_table


class TestCorrectEvaluation(unittest.TestCase):

    def test_integer_arithmetic(self):
        results, _ = _analyze("3 + 5 * 2")
        self.assertEqual(results[0], 13)   # not 16 — precedence matters

    def test_parentheses_override(self):
        results, _ = _analyze("(2 + 3) * 4")
        self.assertEqual(results[0], 20)

    def test_left_associativity(self):
        # 10 - 4 - 2  should be (10-4)-2 = 4, not 10-(4-2) = 8
        results, _ = _analyze("10 - 4 - 2")
        self.assertEqual(results[0], 4)

    def test_float_arithmetic(self):
        results, _ = _analyze("1.5 + 0.5")
        self.assertAlmostEqual(results[0], 2.0)

    def test_integer_division(self):
        results, _ = _analyze("10 / 4")
        self.assertAlmostEqual(results[0], 2.5)

    def test_complex_expression(self):
        results, _ = _analyze("2 * 3 + 4 * 5")
        self.assertEqual(results[0], 26)


class TestAssignmentAndSymbolTable(unittest.TestCase):

    def test_simple_assignment(self):
        _, table = _analyze("x = 10")
        self.assertEqual(table["x"], 10)

    def test_variable_used_after_assignment(self):
        results, table = _analyze("x = 10; y = x + 5")
        self.assertEqual(table["x"], 10)
        self.assertEqual(table["y"], 15)

    def test_variable_reassignment(self):
        _, table = _analyze("x = 3; x = x * 2")
        self.assertEqual(table["x"], 6)

    def test_multiple_variables(self):
        _, table = _analyze("a = 1; b = 2; c = a + b")
        self.assertEqual(table["c"], 3)

    def test_chained_expressions(self):
        results, _ = _analyze("1 + 2; 3 * 4")
        self.assertEqual(results[0], 3)
        self.assertEqual(results[1], 12)


class TestSemanticErrors(unittest.TestCase):

    def test_undefined_variable(self):
        with self.assertRaisesRegex(SemanticError, "Undefined variable"):
            _analyze("z + 1")

    def test_variable_used_before_assignment(self):
        with self.assertRaisesRegex(SemanticError, "Undefined variable"):
            _analyze("y + 1; y = 5")

    def test_division_by_zero(self):
        with self.assertRaisesRegex(SemanticError, "Division by zero"):
            _analyze("10 / 0")

    def test_division_by_zero_expression(self):
        with self.assertRaisesRegex(SemanticError, "Division by zero"):
            _analyze("10 / (3 - 3)")

    def test_undefined_in_complex_expr(self):
        with self.assertRaisesRegex(SemanticError, "Undefined variable"):
            _analyze("x = 1; y = x + unknown")


class TestScopeManagement(unittest.TestCase):
    """Tests for the scoped symbol table (integrated from reference impl.)"""

    def test_push_pop_scope_does_not_leak(self):
        analyzer = SemanticAnalyzer()
        analyzer.push_scope()
        analyzer.scopes[-1]["temp"] = 42
        analyzer.pop_scope()
        # 'temp' must not be visible in the outer scope
        self.assertNotIn("temp", analyzer.symbol_table)

    def test_inner_scope_can_read_outer_variable(self):
        analyzer = SemanticAnalyzer()
        analyzer.scopes[0]["x"] = 10
        analyzer.push_scope()
        # _resolve should find 'x' in the outer scope
        self.assertEqual(analyzer._resolve("x"), 10)
        analyzer.pop_scope()

    def test_inner_scope_shadows_outer(self):
        analyzer = SemanticAnalyzer()
        analyzer.scopes[0]["x"] = 10
        analyzer.push_scope()
        analyzer.scopes[-1]["x"] = 99   # shadow
        self.assertEqual(analyzer._resolve("x"), 99)
        analyzer.pop_scope()
        # After pop, outer value is visible again
        self.assertEqual(analyzer._resolve("x"), 10)


if __name__ == "__main__":
    unittest.main()
