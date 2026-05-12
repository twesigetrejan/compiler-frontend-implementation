# compiler/visualizer.py
# ─────────────────────────────────────────────────────────────
# AST Graphical Visualizer
#
# Generates a self-contained HTML file containing SVG trees —
# circles for nodes, arrows for edges — one tree per top-level
# statement.  The output is saved to disk and can be opened in
# any web browser.
#
# Usage (via main.py):
#   python main.py --visual "3 + 5 * 2"
#   python main.py --visual --bottom-up "x = 10; y = x + 5"
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import math
from pathlib import Path

from compiler.ast_nodes import (
    ASTNode, Assign, BinOp, Identifier, Number, PrintStmt, Program,
)
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.bottom_up_parser import BottomUpParser


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
        if isinstance(n.node, BinOp):
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
# Step 5 — assemble the full HTML page
# ══════════════════════════════════════════════════════════════

def _generate_html(program: Program, source: str, parser_name: str) -> str:
    cards: list[str] = []
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

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AST — {source_html}</title>
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

  /* ── Layout ── */
  .container {{
    display: flex;
    flex-wrap: wrap;
    gap: 28px;
    padding: 32px 36px;
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
    padding: 0 36px 28px;
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
  <h1>Abstract Syntax Tree</h1>
  <div class="meta">
    Input: <span>{source_html}</span>
    &nbsp;&nbsp;Parser: {parser_name}
  </div>
</div>

<div class="container">
  {"".join(cards)}
</div>

<div class="legend">
  <div class="legend-item">
    <div class="legend-circle op"></div>
    Operator node (BinOp)
  </div>
  <div class="legend-item">
    <div class="legend-circle val"></div>
    Value / Identifier
  </div>
  <div class="legend-item">
    <div class="legend-circle stmt"></div>
    Statement (Assign / Print)
  </div>
</div>

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
    Run the lexer + parser on `source`, then generate an HTML AST
    visualization.  Saves the file to `out_path` (defaults to
    ast_visual.html in the current directory).

    Returns the path of the saved file.
    """
    tokens, lex_errors = Lexer(source).tokenize()
    if lex_errors:
        raise ValueError(f"Lexer errors — cannot visualize:\n" +
                         "\n".join(str(e) for e in lex_errors))

    if use_bottom_up:
        program     = BottomUpParser(tokens).parse()
        parser_name = "Shift-Reduce &nbsp;(bottom-up, operator-precedence)"
    else:
        program     = Parser(tokens).parse()
        parser_name = "Recursive Descent &nbsp;(top-down, LL(1))"

    html = _generate_html(program, source, parser_name)

    if out_path is None:
        out_path = Path("ast_visual.html")
    out_path.write_text(html, encoding="utf-8")
    return out_path
