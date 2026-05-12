# compiler/visualizer.py
# ─────────────────────────────────────────────────────────────
# AST Graphical Visualizer
#
# Generates a self-contained HTML file containing SVG trees —
# circles for nodes, arrows for edges — one tree per top-level
# statement.  The output is saved to disk and can be opened in
# any web browser.
#
# Additionally captures and displays all compilation phases:
#   • Lexical analysis (tokens)
#   • Syntax analysis (AST)
#   • Semantic analysis (symbol table, evaluation results)
#
# Usage (via main.py):
#   python main.py --visual "3 + 5 * 2"
#   python main.py --visual --bottom-up "x = 10; y = x + 5"
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program, UnaryOp,
    format_ast,
)
from compiler.lexer import Lexer, format_tokens
from compiler.parser import Parser, ParseError
from compiler.bottom_up_parser import BottomUpParser, BottomUpParseError
from compiler.semantic import SemanticAnalyzer, SemanticError
from compiler.tokens import TokenType


# ── Layout constants ────────────────────────────────────────────
_H      = 100   # pixels per width unit  (horizontal spacing)
_V      = 110   # pixels per depth level (vertical spacing)
_R      = 30    # node circle radius
_PAD    = 50    # canvas padding on each side


# ══════════════════════════════════════════════════════════════
# Step 1 — extract label and children from each AST node type
# ══════════════════════════════════════════════════════════════

def _label(node: ASTNode) -> str:
    if isinstance(node, BinOp):
        return node.op
    if isinstance(node, UnaryOp):
        return f"{node.op}_"  # Unary operator label
    if isinstance(node, Number):
        v = node.value
        # Show 3.0 as "3" for cleaner display
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, Assign):
        return f"{node.name} ="
    if isinstance(node, PrintStmt):
        return "print"
    return "?"


def _children(node: ASTNode) -> list[ASTNode]:
    if isinstance(node, BinOp):
        return [node.left, node.right]
    if isinstance(node, UnaryOp):
        return [node.value]
    if isinstance(node, Assign):
        return [node.value]
    if isinstance(node, PrintStmt):
        return [node.expression]
    return []


# ══════════════════════════════════════════════════════════════
# Step 2 — layout tree (wraps ASTNode with position info)
# ══════════════════════════════════════════════════════════════

class _L:
    """Layout node — pairs an ASTNode with computed (x, width, depth)."""
    __slots__ = ("node", "depth", "label", "children", "x", "width")

    def __init__(self, node: ASTNode, depth: int) -> None:
        self.node     = node
        self.depth    = depth
        self.label    = _label(node)
        self.children: list[_L] = []
        self.x: float  = 0.0
        self.width: float = 1.0


def _build(node: ASTNode, depth: int = 0) -> _L:
    """Recursively build the layout tree."""
    ln = _L(node, depth)
    ln.children = [_build(c, depth + 1) for c in _children(node)]
    return ln


def _measure(ln: _L) -> None:
    """Bottom-up pass: assign width = sum of children widths (min 1)."""
    for c in ln.children:
        _measure(c)
    if ln.children:
        ln.width = max(1.0, sum(c.width for c in ln.children))
    else:
        ln.width = 1.0


def _place(ln: _L, x_off: float = 0.0) -> None:
    """Top-down pass: assign x positions after widths are known."""
    if not ln.children:
        ln.x = x_off + 0.5
        return
    cur = x_off
    for c in ln.children:
        _place(c, cur)
        cur += c.width
    # Parent is centred over its children
    ln.x = (ln.children[0].x + ln.children[-1].x) / 2.0


def _flatten(ln: _L) -> list[_L]:
    """Pre-order list of all layout nodes."""
    result = [ln]
    for c in ln.children:
        result.extend(_flatten(c))
    return result


def _max_depth(ln: _L) -> int:
    if not ln.children:
        return ln.depth
    return max(_max_depth(c) for c in ln.children)


# ══════════════════════════════════════════════════════════════
# Step 3 — render one statement as an SVG element
# ══════════════════════════════════════════════════════════════

def _stmt_svg(stmt: ASTNode, svg_id: str) -> tuple[str, int, int]:
    """
    Returns (svg_string, width_px, height_px).
    svg_id is used to make the arrowhead marker ID unique per SVG.
    """
    ln = _build(stmt)
    _measure(ln)
    _place(ln)

    w_px = int(ln.width * _H) + _PAD * 2
    h_px = int((_max_depth(ln) + 1) * _V) + _PAD * 2

    def px(x: float) -> int:
        return int(x * _H) + _PAD

    def py(d: int) -> int:
        return int(d * _V) + _PAD

    marker_id = f"arr_{svg_id}"
    parts: list[str] = []

    # ── SVG header + arrowhead marker ──────────────────────
    parts.append(
        f'<svg width="{w_px}" height="{h_px}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>'
        f'<marker id="{marker_id}" markerWidth="10" markerHeight="7" '
        f'refX="9" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 10 3.5, 0 7" fill="#555"/>'
        f'</marker>'
        f'</defs>'
    )

    nodes = _flatten(ln)

    # ── Edges (drawn first so circles sit on top) ──────────
    for n in nodes:
        for child in n.children:
            x1, y1 = px(n.x),     py(n.depth)
            x2, y2 = px(child.x), py(child.depth)
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy) or 1.0
            nx_, ny_ = dx / dist, dy / dist
            # Start from the circle edge, stop just before the child circle
            sx, sy = x1 + nx_ * _R,        y1 + ny_ * _R
            ex, ey = x2 - nx_ * (_R + 2),  y2 - ny_ * (_R + 2)
            parts.append(
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" '
                f'x2="{ex:.1f}" y2="{ey:.1f}" '
                f'stroke="#555" stroke-width="2.2" '
                f'marker-end="url(#{marker_id})"/>'
            )

    # ── Node circles and labels ─────────────────────────────
    for n in nodes:
        cx, cy = px(n.x), py(n.depth)

        # Operator nodes get a light tint so they stand out
        if isinstance(n.node, (BinOp, UnaryOp)):
            fill = "#fff"
            stroke_color = "#1a1a2e"
            stroke_w = "3"
        elif isinstance(n.node, (Assign, PrintStmt)):
            fill = "#fff"
            stroke_color = "#2c3e50"
            stroke_w = "2.5"
        else:
            fill = "#fff"
            stroke_color = "#555"
            stroke_w = "2"

        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{_R}" '
            f'fill="{fill}" stroke="{stroke_color}" stroke-width="{stroke_w}"/>'
        )

        # Shrink font for longer labels (e.g. "x =" or "result")
        font_size = 13 if len(n.label) > 4 else (15 if len(n.label) > 2 else 19)
        parts.append(
            f'<text x="{cx}" y="{cy}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'font-family="Georgia,serif" font-size="{font_size}" '
            f'font-weight="bold" fill="#111">'
            f'{n.label}</text>'
        )

    parts.append('</svg>')
    return ''.join(parts), w_px, h_px


# ══════════════════════════════════════════════════════════════
# Step 4 — reconstruct a readable source string from the AST
# ══════════════════════════════════════════════════════════════

def _src(node: ASTNode) -> str:
    """Rebuild a compact source string from an AST node (for card labels)."""
    if isinstance(node, BinOp):
        return f"{_src(node.left)} {node.op} {_src(node.right)}"
    if isinstance(node, UnaryOp):
        return f"{node.op}{_src(node.value)}"
    if isinstance(node, Number):
        v = node.value
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, Assign):
        return f"{node.name} = {_src(node.value)}"
    if isinstance(node, PrintStmt):
        return f"print({_src(node.expression)})"
    return "?"


# ══════════════════════════════════════════════════════════════
# Step 5 — assemble the full HTML page with all compilation phases
# ══════════════════════════════════════════════════════════════

def _generate_html(
    program: Program | None,
    source: str,
    parser_name: str,
    tokens: list = None,
    ast_text: str = "",
    symbol_table: dict = None,
    evaluation_results: list = None,
    lex_errors: list = None,
    lex_error_text: str = "",
    parse_error_text: str = "",
    semantic_error: str = "",
) -> str:
    """Generate HTML with all compilation phases and visual AST, including errors."""
    
    cards: list[str] = []
    if program is not None:
        for i, stmt in enumerate(program.statements):
            svg_str, _w, _h = _stmt_svg(stmt, svg_id=str(i))
            label = _src(stmt)
            cards.append(
                f'<div class="card">'
                f'<div class="card-title">Statement {i + 1}'
                f'<span class="card-expr">{label}</span></div>'
                f'{svg_str}'
                f'</div>'
            )

    # Escape source for HTML display
    source_html = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Format tokens section
    tokens_html = ""
    if tokens or lex_error_text:
        if lex_error_text:
            non_eof = [t for t in tokens if t.type != TokenType.EOF] if tokens else []
            tokens_lines = format_tokens(tokens).split("\n") if tokens else []
            tokens_html = f'''
    <div class="section" id="phase-1">
      <h2>Phase 1 — Lexical Analysis</h2>
      <div class="phase-content">
        <p class="phase-info">Tokenized input using regex patterns for numbers, identifiers, and operators.</p>
        <pre class="output">{chr(10).join(tokens_lines)}</pre>
        <p class="phase-info">✓ {len(non_eof)} token(s) produced.</p>
        <h3 style="color: #e74c3c; margin-top: 16px;">✗ Lexical Errors:</h3>
        <pre class="output error">{lex_error_text}</pre>
      </div>
    </div>
            '''
        else:
            non_eof = [t for t in tokens if t.type != TokenType.EOF]
            tokens_lines = format_tokens(tokens).split("\n")
            tokens_html = f'''
    <div class="section" id="phase-1">
      <h2>Phase 1 — Lexical Analysis</h2>
      <div class="phase-content">
        <p class="phase-info">Tokenized input using regex patterns for numbers, identifiers, and operators.</p>
        <pre class="output">{chr(10).join(tokens_lines)}</pre>
        <p class="result">✓ {len(non_eof)} token(s) produced.</p>
      </div>
    </div>
            '''
    
    # Format AST section
    ast_html = ""
    if ast_text or parse_error_text:
        if parse_error_text:
            ast_lines = ast_text.split("\n") if ast_text else []
            ast_html = f'''
    <div class="section" id="phase-2">
      <h2>Phase 2 — Syntax Analysis</h2>
      <div class="phase-content">
        <p class="phase-info">Parser: {parser_name}</p>
        <p class="phase-info">Associativity: Left-to-right for all binary operators</p>
        <p class="phase-info">Precedence: +/- &lt; */ &lt; () &lt; atoms (low → high)</p>
        <h3 style="color: #e74c3c; margin-top: 16px;">✗ Parse Error:</h3>
        <pre class="output error">{parse_error_text}</pre>
      </div>
    </div>
            '''
        else:
            ast_lines = ast_text.split("\n")
            ast_html = f'''
    <div class="section" id="phase-2">
      <h2>Phase 2 — Syntax Analysis</h2>
      <div class="phase-content">
        <p class="phase-info">Parser: {parser_name}</p>
        <p class="phase-info">Associativity: Left-to-right for all binary operators</p>
        <p class="phase-info">Precedence: +/- &lt; */ &lt; () &lt; atoms (low → high)</p>
        <h3>Abstract Syntax Tree:</h3>
        <pre class="output">{chr(10).join('  ' + line for line in ast_lines)}</pre>
        <p class="result">✓ AST built successfully.</p>
      </div>
    </div>
            '''
    
    # Format semantic analysis section
    semantic_html = ""
    if symbol_table is not None or evaluation_results or semantic_error:
        semantic_content = '<div class="phase-content"><p class="phase-info">Checks: undefined variables | division by zero | type consistency</p>'
        
        if semantic_error:
            semantic_content += f'''
        <h3 style="color: #e74c3c; margin-top: 16px;">✗ Semantic Error:</h3>
        <pre class="output error">{semantic_error}</pre>
            '''
        else:
            if symbol_table:
                semantic_content += '<h3>Symbol table (global scope):</h3><pre class="output">'
                for name, val in symbol_table.items():
                    semantic_content += f"  {name}  =  {val}\n"
                semantic_content += '</pre>'
            
            if evaluation_results:
                numeric_results = [(i + 1, r) for i, r in enumerate(evaluation_results) if r is not None]
                if numeric_results:
                    semantic_content += '<h3>Evaluation results:</h3><pre class="output">'
                    for idx, val in numeric_results:
                        semantic_content += f"  statement {idx}  →  {val}\n"
                    semantic_content += '</pre>'
            
            semantic_content += '<p class="result">✓ Semantic analysis passed.</p>'
        
        semantic_content += '</div>'
        
        semantic_html = f'''
    <div class="section" id="phase-3">
      <h2>Phase 3 — Semantic Analysis</h2>
      {semantic_content}
    </div>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AST & Compilation Phases — {source_html}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  
  body {{
    background: #eef0f3;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    min-height: 100vh;
  }}

  /* ── Banner ── */
  .banner {{
    background: #1a1a2e;
    color: #ddd;
    padding: 22px 36px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  
  .banner h1 {{
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    letter-spacing: .4px;
  }}
  
  .banner .meta {{
    font-size: 13px;
    color: #999;
  }}
  
  .banner .meta span {{
    background: #2d2d4a;
    color: #e0e0ff;
    font-family: "Courier New", monospace;
    font-size: 13px;
    padding: 2px 10px;
    border-radius: 4px;
    border: 1px solid #44447a;
  }}

  /* ── Tabs Navigation ── */
  .tabs {{
    background: #2c2c3d;
    display: flex;
    gap: 2px;
    padding: 0 36px;
    border-bottom: 1px solid #444;
  }}
  
  .tab {{
    padding: 14px 18px;
    background: transparent;
    color: #999;
    border: none;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
    border-bottom: 2px solid transparent;
  }}
  
  .tab:hover {{
    color: #ddd;
  }}
  
  .tab.active {{
    color: #fff;
    border-bottom-color: #64b5f6;
  }}

  /* ── Content Area ── */
  .content {{
    padding: 32px 36px;
  }}
  
  .section {{
    display: none;
  }}
  
  .section.active {{
    display: block;
  }}
  
  .section h2 {{
    font-size: 18px;
    color: #333;
    margin-bottom: 16px;
    border-bottom: 2px solid #ddd;
    padding-bottom: 10px;
  }}
  
  .section h3 {{
    font-size: 14px;
    color: #555;
    margin-top: 16px;
    margin-bottom: 8px;
    font-weight: 600;
  }}
  
  .phase-content {{
    background: #f8f9fa;
    padding: 16px;
    border-radius: 8px;
    border-left: 3px solid #64b5f6;
  }}
  
  .phase-info {{
    font-size: 12px;
    color: #666;
    margin: 8px 0;
    font-style: italic;
  }}
  
  .output {{
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 12px;
    font-family: "Courier New", monospace;
    font-size: 12px;
    color: #333;
    overflow-x: auto;
    margin: 10px 0;
    line-height: 1.5;
  }}
  
  .result {{
    color: #27ae60;
    font-weight: 600;
    font-size: 13px;
    margin-top: 12px;
  }}
  
  .output.error {{
    border-left: 3px solid #e74c3c;
    color: #c0392b;
    background: #fdf2f2;
  }}

  /* ── Layout ── */
  .container {{
    display: flex;
    flex-wrap: wrap;
    gap: 28px;
    align-items: flex-start;
  }}

  /* ── Cards ── */
  .card {{
    background: #fff;
    border-radius: 14px;
    padding: 20px 22px;
    box-shadow: 0 2px 14px rgba(0,0,0,.09);
    display: inline-flex;
    flex-direction: column;
    gap: 14px;
  }}
  
  .card-title {{
    font-size: 13px;
    font-weight: 600;
    color: #666;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  
  .card-expr {{
    background: #f5f5f5;
    color: #c0392b;
    font-family: "Courier New", monospace;
    font-size: 13px;
    padding: 2px 10px;
    border-radius: 5px;
    font-weight: 500;
  }}

  /* ── Legend ── */
  .legend {{
    padding: 28px 36px 0;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }}
  
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #555;
  }}
  
  .legend-circle {{
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #fff;
    display: inline-block;
    flex-shrink: 0;
  }}
  
  .legend-circle.op   {{ border: 3px solid #1a1a2e; }}
  .legend-circle.val  {{ border: 2px solid #555; }}
  .legend-circle.stmt {{ border: 2.5px solid #2c3e50; }}
</style>
</head>
<body>

<div class="banner">
  <h1>Compiler Visualization</h1>
  <div class="meta">
    Input: <span>{source_html}</span>
    &nbsp;&nbsp;Parser: {parser_name}
  </div>
</div>

<div class="tabs">
  <button class="tab active" onclick="showTab('phase-1')">Lexical Analysis</button>
  <button class="tab" onclick="showTab('phase-2')">Syntax Analysis</button>
  <button class="tab" onclick="showTab('phase-3')">Semantic Analysis</button>
  <button class="tab" onclick="showTab('visual')">Visual AST</button>
</div>

<div class="content">
  {tokens_html}
  {ast_html}
  {semantic_html}
  
  <div class="section active" id="visual">
    <h2>Visual Abstract Syntax Tree</h2>
    <div class="phase-content">
      <p class="phase-info">Graphical representation of each statement's AST structure.</p>
      {f'<div class="container">{"".join(cards)}</div>' if cards else '<p class="phase-info" style="color: #e74c3c;">No AST available due to errors in earlier compilation phases. Check the Lexical Analysis and Syntax Analysis tabs for details.</p>'}
    </div>
  </div>
</div>

<script>
function showTab(tabId) {{
  // Hide all sections
  const sections = document.querySelectorAll('.section');
  sections.forEach(s => s.classList.remove('active'));
  
  // Show selected section
  const selected = document.getElementById(tabId);
  if (selected) selected.classList.add('active');
  
  // Update tab buttons
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
}}
</script>

</body>
</html>'''


# ══════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════

def visualize_source(
    source: str,
    use_bottom_up: bool = False,
    out_path: Path | None = None,
) -> Path:
    """
    Run the full front-end pipeline on `source`, then generate an HTML
    visualization with all compilation phases (lexical, syntax, semantic)
    plus the graphical AST representation.

    If out_path is None, generates a unique filename using timestamp:
      ast_visual_YYYYMMDD_HHMMSS.html
    
    Returns the path of the saved file.
    """
    # ─────────────────────────────────────────────────────────────
    # PHASE 1 — LEXICAL ANALYSIS
    # ─────────────────────────────────────────────────────────────
    tokens, lex_errors = Lexer(source).tokenize()
    lex_error_text = "\n".join(str(e) for e in lex_errors) if lex_errors else None

    # ─────────────────────────────────────────────────────────────
    # PHASE 2 — SYNTAX ANALYSIS
    # ─────────────────────────────────────────────────────────────
    program = None
    parse_error_text = None
    ast_text = ""

    if not lex_errors:
        parser_name = "Shift-Reduce &nbsp;(bottom-up, operator-precedence)" if use_bottom_up else "Recursive Descent &nbsp;(top-down, LL(1))"
        try:
            if use_bottom_up:
                program     = BottomUpParser(tokens).parse()
            else:
                program     = Parser(tokens).parse()
            ast_text = format_ast(program)
        except (ParseError, BottomUpParseError) as err:
            parse_error_text = str(err)
    else:
        parser_name = "Shift-Reduce &nbsp;(bottom-up, operator-precedence)" if use_bottom_up else "Recursive Descent &nbsp;(top-down, LL(1))"

    # ─────────────────────────────────────────────────────────────
    # PHASE 3 — SEMANTIC ANALYSIS
    # ─────────────────────────────────────────────────────────────
    symbol_table = None
    evaluation_results = None
    semantic_error_text = None

    if program is not None:
        try:
            analyzer = SemanticAnalyzer()
            results  = analyzer.analyze(program)
            symbol_table = dict(analyzer.symbol_table) if analyzer.symbol_table else {}
            evaluation_results = results
        except SemanticError as err:
            semantic_error_text = str(err)

    # Generate the enhanced HTML
    html = _generate_html(
        program=program,
        source=source,
        parser_name=parser_name,
        tokens=tokens if not lex_errors else None,
        ast_text=ast_text,
        symbol_table=symbol_table,
        evaluation_results=evaluation_results,
        lex_errors=lex_errors,
        lex_error_text=lex_error_text,
        parse_error_text=parse_error_text,
        semantic_error=semantic_error_text,
    )

    # Generate unique filename if not provided
    if out_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"ast_visual_{timestamp}.html")
    
    out_path.write_text(html, encoding="utf-8")
    return out_path
