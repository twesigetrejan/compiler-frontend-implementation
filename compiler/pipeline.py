# compiler/pipeline.py
# ─────────────────────────────────────────────────────────────
# Unified front-end compiler pipeline.
#
# compile_source() wires all three phases together and prints a
# structured report that labels every phase, shows what it
# produced (or where it failed), and always states which parser
# was used.
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

from compiler.ast_nodes import format_ast
from compiler.bottom_up_parser import BottomUpParser, BottomUpParseError, PRECEDENCE
from compiler.lexer import RE1_NUMBER, RE2_IDENTIFIER, RE3_OPERATOR, Lexer, format_tokens
from compiler.parser import Parser, ParseError
from compiler.semantic import SemanticAnalyzer, SemanticError
from compiler.tokens import TokenType

_BAR  = "=" * 64
_DASH = "-" * 64
_TICK = "  ✓"
_CROSS= "  ✗"


def _analyze_grammar(tokens: list) -> tuple[str, str]:
    """
    Analyze the token stream to determine optimal parser.
    
    Returns: (parser_choice, reasoning)
    
    Criteria:
    - TOP-DOWN (LL(1)): Simple, LL(1)-compatible grammars. Better error messages.
    - BOTTOM-UP (LR(1)): Complex operator precedence, high operator density.
    """
    # Count token types
    non_eof = [t for t in tokens if t.type != TokenType.EOF]
    if not non_eof:
        return "top-down", "Empty input"
    
    # Count operators and operands
    operators = {TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY, 
                 TokenType.DIVIDE, TokenType.LPAREN, TokenType.RPAREN}
    operator_count = sum(1 for t in non_eof if t.type in operators)
    operand_count = sum(1 for t in non_eof if t.type in 
                       {TokenType.NUMBER, TokenType.IDENTIFIER})
    
    # Check for assignment (more complex)
    has_assignment = any(t.type == TokenType.ASSIGN for t in non_eof)
    
    # Calculate metrics
    operator_density = operator_count / len(non_eof) if non_eof else 0
    
    # Criteria for parser selection
    reasons = []
    
    # Simple heuristic: if operator density is high, bottom-up is better
    # because it handles operator precedence more naturally
    if operator_density >= 0.35:
        reasons.append(f"High operator density ({operator_density:.1%})")
        return "bottom-up", " + ".join(reasons)
    
    # If has complex patterns (multiple operators), consider bottom-up
    if operator_count >= 3:
        reasons.append(f"Multiple operators ({operator_count})")
        # But still prefer top-down for simplicity unless very high density
        if operator_density >= 0.25:
            return "bottom-up", " + ".join(reasons)
    
    # Default to top-down: simpler, better error messages, sufficient for LL(1)
    reasons.append("Simple grammar (LL(1) compatible)")
    if not has_assignment:
        reasons.append("Primarily expression-based")
    
    return "top-down", " + ".join(reasons)


def _format_error_with_context(message: str, source: str, line: int | None = None, column: int | None = None) -> str:
    """Format an error message with source context (line, column, and source snippet)."""
    # Remove position info from message if it's already there
    import re
    message_clean = re.sub(r'\s+at line \d+, column \d+$', '', message)
    error_str = message_clean
    
    if line is not None and column is not None:
        error_str += f" at line {line}, column {column}"
        
        # Extract the source line
        source_lines = source.split('\n')
        if 0 < line <= len(source_lines):
            source_line = source_lines[line - 1]
            # Add the source line and a caret pointing to the error
            error_str += f"\n    {source_line}\n    {' ' * (column - 1)}^"
    elif line is not None:
        error_str += f" at line {line}"
    
    return error_str


def compile_source(source: str, use_bottom_up: bool | None = None) -> str:
    """
    Run the full front-end pipeline on `source` and print a
    phase-by-phase report.

    Parameters
    ----------
    source        : the program text to compile
    use_bottom_up : if True, use shift-reduce parser; if False, use recursive descent.
                    if None (default), automatically select based on grammar analysis.
    
    Returns
    -------
    str : "top-down" or "bottom-up" indicating which parser was used
    """
    # Auto-detect parser if not specified
    tokens_for_analysis, _ = Lexer(source).tokenize()
    
    if use_bottom_up is None:
        auto_parser, reasoning = _analyze_grammar(tokens_for_analysis)
        use_bottom_up = (auto_parser == "bottom-up")
        selection_info = f" (auto-selected: {reasoning})"
    else:
        selection_info = " (explicitly specified)"
    
    parser_name = (
        "Shift-Reduce  (bottom-up, operator-precedence)"
        if use_bottom_up else
        "Recursive Descent  (top-down, LL(1))"
    )

    print(_BAR)
    print("  FRONT-END COMPILER")
    print(f"  Parser : {parser_name}{selection_info}")
    print(_BAR)
    print(f"  Input  : {source!r}")
    print()

    # ═══════════════════════════════════════════════════════
    # PHASE 1 — LEXICAL ANALYSIS
    # ═══════════════════════════════════════════════════════
    print(_DASH)
    print("  PHASE 1 · LEXICAL ANALYSIS")
    print(_DASH)
    print(f"  RE1 (numbers)     :  {RE1_NUMBER}")
    print(f"  RE2 (identifiers) :  {RE2_IDENTIFIER}")
    print(f"  RE3 (operators)   :  {RE3_OPERATOR}")
    print("  Master pattern    :  RE1 | RE2 | RE3  (comments & whitespace stripped)")
    print()

    tokens, lex_errors = Lexer(source).tokenize()

    if lex_errors:
        for err in lex_errors:
            formatted = _format_error_with_context(str(err), source, err.line, err.column)
            print(f"{_CROSS} {formatted}")
        print()
        print("  Lexical errors found — compilation halted.")
        print(_BAR)
        return "bottom-up" if use_bottom_up else "top-down"

    print(format_tokens(tokens))
    print()
    non_eof = [t for t in tokens if t.type != TokenType.EOF]
    print(f"{_TICK} {len(non_eof)} token(s) produced.")
    print()

    # ═══════════════════════════════════════════════════════
    # PHASE 2 — SYNTAX ANALYSIS
    # ═══════════════════════════════════════════════════════
    print(_DASH)
    print("  PHASE 2 · SYNTAX ANALYSIS")
    print(_DASH)
    print(f"  Parser        : {parser_name}")
    print("  Associativity : Left-to-right for all binary operators")
    print("  Precedence    : +/-  <  */  <  ()  <  atoms  (low → high)")

    if use_bottom_up:
        prec_table = "  " + "  |  ".join(
            f"{tt.name}={p}" for tt, p in PRECEDENCE.items()
        )
        print(f"  Prec. table   : {prec_table}")
    print()

    try:
        if use_bottom_up:
            ast = BottomUpParser(tokens).parse()
        else:
            ast = Parser(tokens).parse()
    except (ParseError, BottomUpParseError) as err:
        formatted = _format_error_with_context(str(err), source, err.line, err.column)
        print(f"{_CROSS} {formatted}")
        print()
        print("  Syntax error found — compilation halted.")
        print(_BAR)
        return "bottom-up" if use_bottom_up else "top-down"

    print("  Abstract Syntax Tree:")
    print()
    for line in format_ast(ast).splitlines():
        print(f"    {line}")
    print()
    print(f"{_TICK} AST built successfully.")
    print()

    # ═══════════════════════════════════════════════════════
    # PHASE 3 — SEMANTIC ANALYSIS
    # ═══════════════════════════════════════════════════════
    print(_DASH)
    print("  PHASE 3 · SEMANTIC ANALYSIS")
    print(_DASH)
    print("  Checks : undefined variables  |  division by zero  |  type consistency")
    print("  Scopes : push on block entry, pop on block exit  (variable shadowing)")
    print()

    try:
        analyzer = SemanticAnalyzer()
        results  = analyzer.analyze(ast)
    except SemanticError as err:
        # For semantic errors, include position info if available
        if hasattr(err, 'line') and err.line is not None:
            formatted = _format_error_with_context(str(err), source, err.line, err.column)
        else:
            # No position info available, show source for context
            formatted = f"{err}\n\n    Source: {source}"
        print(f"{_CROSS} {formatted}")
        print()
        print("  Semantic error found — compilation halted.")
        print(_BAR)
        return "bottom-up" if use_bottom_up else "top-down"

    if analyzer.symbol_table:
        print("  Symbol table (global scope):")
        for name, val in analyzer.symbol_table.items():
            print(f"    {name}  =  {val}")
        print()

    numeric_results = [(i + 1, r) for i, r in enumerate(results) if r is not None]
    if numeric_results:
        print("  Evaluation results:")
        for idx, val in numeric_results:
            print(f"    statement {idx}  →  {val}")
        print()

    print(f"{_TICK} Semantic analysis passed.")
    print(_BAR)
    print()
    
    return "bottom-up" if use_bottom_up else "top-down"
