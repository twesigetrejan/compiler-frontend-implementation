# -*- coding: utf-8 -*-
# compiler/report.py
# Full HTML report generator — all test cases, both parsers,
# every phase, grammar tables, FIRST/FOLLOW, LL(1) table,
# precedence table, parse steps, symbol table.

from __future__ import annotations
import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from compiler.ast_nodes import ASTNode, Program, format_ast
from compiler.bottom_up_parser import BottomUpParser, BottomUpParseError
from compiler.grammar_tables import (
    render_grammar_html, render_first_follow_html,
    render_ll1_table_html, render_precedence_table_html,
    render_reduce_rules_html,
)
from compiler.lexer import Lexer, LexerError, RE1_NUMBER, RE2_IDENTIFIER, RE3_OPERATOR
from compiler.parser import Parser, ParseError
from compiler.semantic import SemanticAnalyzer, SemanticError
from compiler.tokens import Token, TokenType
from compiler.visualizer import _stmt_svg, _src


# ── Data model ────────────────────────────────────────────────

@dataclass
class PhaseResult:
    passed: bool
    error: str = ""
    line: int | None = None
    column: int | None = None

@dataclass
class CaseResult:
    index: int
    description: str
    source: str
    parser_mode: str

    ph1: PhaseResult | None = None
    tokens: list[Token] = field(default_factory=list)

    ph2: PhaseResult | None = None
    ast: Program | None = None
    parse_steps: list[str] = field(default_factory=list)

    ph3: PhaseResult | None = None
    symbol_table: dict[str, Any] = field(default_factory=dict)
    eval_results: list[Any] = field(default_factory=list)
    print_outputs: list[Any] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.ph1 and not self.ph1.passed:   return "LEXER ERROR"
        if self.ph2 and not self.ph2.passed:   return "PARSER ERROR"
        if self.ph3 and not self.ph3.passed:   return "SEMANTIC ERROR"
        return "PASS"


# ── Pipeline runner ───────────────────────────────────────────

def _run(index: int, description: str, source: str, use_bottom_up: bool) -> CaseResult:
    mode   = "Bottom-Up" if use_bottom_up else "Top-Down"
    result = CaseResult(index=index, description=description,
                        source=source, parser_mode=mode)

    tokens, lex_errors = Lexer(source).tokenize()
    result.tokens = tokens
    if lex_errors:
        err = lex_errors[0]  # Get first error
        result.ph1 = PhaseResult(passed=False,
                                 error="\n".join(str(e) for e in lex_errors),
                                 line=err.line, column=err.column)
        return result
    result.ph1 = PhaseResult(passed=True)

    p = None
    try:
        if use_bottom_up:
            p = BottomUpParser(tokens)
            ast = p.parse()
            result.parse_steps = p.steps
        else:
            p = Parser(tokens)
            ast = p.parse()
            result.parse_steps = p.steps
        result.ast = ast
        result.ph2 = PhaseResult(passed=True)
    except (ParseError, BottomUpParseError) as exc:
        result.ph2 = PhaseResult(passed=False, error=str(exc),
                                line=getattr(exc, 'line', None),
                                column=getattr(exc, 'column', None))
        # still capture whatever steps were recorded before the error
        if hasattr(p, 'steps'):
            result.parse_steps = p.steps
        return result

    print_buf: list[Any] = []

    class _Cap(SemanticAnalyzer):
        def analyze(self, node: ASTNode) -> Any:
            from compiler.ast_nodes import PrintStmt
            if isinstance(node, PrintStmt):
                value = self.analyze(node.expression)
                print_buf.append(value)
                return None
            return super().analyze(node)

    try:
        analyzer = _Cap()
        raw = analyzer.analyze(ast)
        result.ph3 = PhaseResult(passed=True)
        result.symbol_table  = dict(analyzer.symbol_table)
        result.eval_results  = [r for r in raw if r is not None]
        result.print_outputs = print_buf
    except SemanticError as exc:
        result.ph3 = PhaseResult(passed=False, error=str(exc),
                                line=getattr(exc, 'line', None),
                                column=getattr(exc, 'column', None))

    return result


# ── HTML helpers ──────────────────────────────────────────────

def _e(s: str) -> str:
    return _html.escape(str(s))

def _format_error_with_source(error: str, source: str, line: int | None = None, column: int | None = None) -> str:
    """Format an error message with source code context and caret."""
    html_parts = [f'<div class="error-formatted">']
    html_parts.append(f'<div class="error-msg-line">{_e(error)}</div>')
    
    if line is not None and column is not None:
        source_lines = source.split('\n')
        if 0 < line <= len(source_lines):
            source_line = source_lines[line - 1]
            caret = ' ' * (column - 1) + '^'
            html_parts.append(
                f'<div class="error-source-code">{_e(source_line)}</div>'
                f'<div class="error-caret-line">{_e(caret)}</div>'
            )
    
    html_parts.append('</div>')
    return "".join(html_parts)

def _badge(status: str) -> str:
    cls = {"PASS":"badge-pass","LEXER ERROR":"badge-lex",
           "PARSER ERROR":"badge-par","SEMANTIC ERROR":"badge-sem"}.get(status,"badge-pass")
    return f'<span class="badge {cls}">{_e(status)}</span>'

def _ph_hdr(num: str, title: str, passed) -> str:
    if passed is None:   icon, cls = "·", "ph-skip"
    elif passed:         icon, cls = "✓", "ph-pass"
    else:                icon, cls = "✗", "ph-fail"
    return (f'<div class="ph-header {cls}">'
            f'<span class="ph-icon">{icon}</span>'
            f'<span class="ph-num">Phase {num}</span>'
            f'<span class="ph-title">{title}</span></div>')

def _token_table(tokens: list[Token]) -> str:
    rows = "".join(
        f"<tr><td>{t.line}:{t.column}</td>"
        f"<td class='tt'>{_e(t.type.name)}</td>"
        f"<td><code>{_e(repr(t.value))}</code></td></tr>"
        for t in tokens if t.type != TokenType.EOF
    )
    count = len([t for t in tokens if t.type != TokenType.EOF])
    return (f"<p class='ph-stat'>{count} token(s) produced</p>"
            f"<table class='tok-tbl'><thead><tr>"
            f"<th>Line:Col</th><th>Type</th><th>Value</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>")

def _ast_visual(program: Program, uid: str) -> str:
    parts = []
    for i, stmt in enumerate(program.statements):
        svg, _, _ = _stmt_svg(stmt, svg_id=f"{uid}_{i}")
        label = _e(_src(stmt))
        parts.append(
            f'<div class="ast-item">'
            f'<div class="ast-item-label">stmt {i+1}: <code>{label}</code></div>'
            f'{svg}</div>')
    return f'<div class="ast-row">{"".join(parts)}</div>'

def _text_ast(program: Program) -> str:
    return f'<pre class="text-ast">{_e(format_ast(program))}</pre>'

def _symbol_table_html(table, results, prints) -> str:
    parts = []
    if table:
        rows = "".join(
            f"<tr><td><code>{_e(k)}</code></td><td><strong>{_e(str(v))}</strong></td></tr>"
            for k, v in table.items()
        )
        parts.append(
            f'<p class="ph3-sub">Symbol Table (global scope)</p>'
            f'<table class="sym-tbl"><thead><tr><th>Variable</th><th>Value</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
    if results:
        rows = "".join(
            f"<tr><td>{i+1}</td><td><strong>{_e(str(v))}</strong></td></tr>"
            for i, v in enumerate(results)
        )
        parts.append(
            f'<p class="ph3-sub">Evaluation Results</p>'
            f'<table class="sym-tbl"><thead><tr><th>Stmt</th><th>Result</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
    if prints:
        items = "".join(f"<li><code>{_e(str(v))}</code></li>" for v in prints)
        parts.append(f'<p class="ph3-sub">print() output</p>'
                     f'<ul class="print-list">{items}</ul>')
    return "".join(parts) if parts else "<p class='empty'>No values produced.</p>"

def _steps_html(steps: list[str]) -> str:
    if not steps:
        return "<p class='empty'>No steps recorded.</p>"
    items = ""
    for s in steps:
        if "SHIFT" in s:        cls = "step-shift"
        elif "REDUCE" in s:     cls = "step-reduce"
        elif "Accept" in s or "✓" in s:  cls = "step-accept"
        elif s.startswith("──"): cls = "step-sep"
        else:                   cls = "step-other"
        items += f'<li class="{cls}">{_e(s)}</li>'
    return f'<ul class="step-list">{items}</ul>'


# ── Case card ─────────────────────────────────────────────────

def _case_card(cr: CaseResult) -> str:
    cid = f"c{cr.index}_{cr.parser_mode.replace('-','')}"
    status = cr.status

    # Phase 1
    ph1_passed = cr.ph1.passed if cr.ph1 else None
    if cr.ph1 is None:
        ph1_body = "<p class='empty'>Phase not reached.</p>"
    elif not cr.ph1.passed:
        ph1_body = _format_error_with_source(cr.ph1.error, cr.source, cr.ph1.line, cr.ph1.column)
    else:
        ph1_body = _token_table(cr.tokens)

    # Phase 2
    ph2_passed = cr.ph2.passed if cr.ph2 else None
    ph2_mode = f"Syntax Analysis ({cr.parser_mode})"
    if cr.ph2 is None:
        ph2_body = "<p class='empty'>Phase not reached.</p>"
    elif not cr.ph2.passed:
        ph2_body = (
            _format_error_with_source(cr.ph2.error, cr.source, cr.ph2.line, cr.ph2.column)
            + (f'<p class="ph3-sub">Parse steps up to error:</p>'
               + _steps_html(cr.parse_steps) if cr.parse_steps else "")
        )
    else:
        ph2_body = (
            _ast_visual(cr.ast, uid=cid)
            + _text_ast(cr.ast)
            + f'<details class="steps-details"><summary>Parse steps ({len(cr.parse_steps)})</summary>'
            + _steps_html(cr.parse_steps)
            + '</details>'
        )

    # Phase 3
    ph3_passed = cr.ph3.passed if cr.ph3 else None
    if cr.ph3 is None:
        ph3_body = "<p class='empty'>Phase not reached.</p>"
    elif not cr.ph3.passed:
        ph3_body = _format_error_with_source(cr.ph3.error, cr.source, cr.ph3.line, cr.ph3.column)
    else:
        ph3_body = _symbol_table_html(cr.symbol_table, cr.eval_results, cr.print_outputs)

    return f'''
<div class="case-card">
  <div class="case-header">
    <span class="case-num">#{cr.index}</span>
    <span class="case-desc">{_e(cr.description)}</span>
    <code class="case-src">{_e(cr.source)}</code>
    {_badge(status)}
  </div>
  <div class="phases">
    <div class="phase-block">
      {_ph_hdr("1", "Lexical Analysis", ph1_passed)}
      <div class="ph-body">{ph1_body}</div>
    </div>
    <div class="phase-block">
      {_ph_hdr("2", ph2_mode, ph2_passed)}
      <div class="ph-body">{ph2_body}</div>
    </div>
    <div class="phase-block">
      {_ph_hdr("3", "Semantic Analysis", ph3_passed)}
      <div class="ph-body">{ph3_body}</div>
    </div>
  </div>
</div>'''


# ── Section (one tab's worth) ─────────────────────────────────

def _section_html(cases: list[CaseResult], is_top_down: bool) -> str:
    total  = len(cases)
    passed = sum(1 for c in cases if c.status == "PASS")
    failed = total - passed

    summary = (
        f'<div class="summary">'
        f'<div class="summary-box"><span class="s-num s-blue">{total}</span>'
        f'<span class="s-lbl">Test cases</span></div>'
        f'<div class="summary-box"><span class="s-num s-green">{passed}</span>'
        f'<span class="s-lbl">Passed</span></div>'
        f'<div class="summary-box"><span class="s-num s-red">{failed}</span>'
        f'<span class="s-lbl">Errors detected</span></div>'
        f'</div>'
    )

    # Theory tables section
    if is_top_down:
        theory = f'''
<div class="theory-section">
  <h3 class="theory-title">Grammar</h3>
  {render_grammar_html()}
  <h3 class="theory-title">FIRST and FOLLOW Sets</h3>
  <p class="theory-note">Computed from the expression sub-grammar:
    E &rarr; T E' &nbsp;|&nbsp; E' &rarr; + T E' | &minus; T E' | &epsilon; &nbsp;|&nbsp;
    T &rarr; F T' &nbsp;|&nbsp; T' &rarr; * F T' | / F T' | &epsilon; &nbsp;|&nbsp;
    F &rarr; ( E ) | id | num</p>
  {render_first_follow_html()}
  <h3 class="theory-title">LL(1) Predictive Parsing Table &mdash; M[A, a]</h3>
  <p class="theory-note">Each cell M[A, a] gives the production to use when non-terminal A
    is on top of the parse stack and token a is the current lookahead.</p>
  <div class="tbl-scroll">{render_ll1_table_html()}</div>
</div>'''
    else:
        theory = f'''
<div class="theory-section">
  <h3 class="theory-title">Grammar (same productions, built bottom-up)</h3>
  {render_grammar_html()}
  <h3 class="theory-title">Reduce Rules</h3>
  <p class="theory-note">These grammar productions become reduce actions when the matching
    pattern appears on the stack top.</p>
  {render_reduce_rules_html()}
</div>'''

    cards = "".join(_case_card(c) for c in cases)
    return summary + theory + '<h3 class="section-cases-title">Test Cases</h3>' + cards


# ── CSS + JS ──────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:#edf0f4;color:#222;min-height:100vh}

.banner{background:#12122a;color:#ccc;padding:24px 40px 20px}
.banner h1{font-size:22px;color:#fff;margin-bottom:6px}
.banner .sub{font-size:13px;color:#888;line-height:1.8}
.banner code{background:#1e1e40;color:#a0c0ff;padding:2px 8px;border-radius:4px;font-size:13px}

.re-bar{background:#1c1c38;padding:12px 40px;font-size:12.5px;color:#9ab;
  display:flex;gap:32px;flex-wrap:wrap}
.re-bar span{color:#cce;font-family:monospace}

.tab-bar{display:flex;gap:4px;padding:20px 40px 0;border-bottom:2px solid #d0d6df}
.tab-btn{padding:10px 28px;border:none;border-radius:8px 8px 0 0;font-size:14px;
  font-weight:600;cursor:pointer;background:#d4dae4;color:#555;transition:background .15s}
.tab-btn.active{background:#fff;color:#12122a;border-bottom:2px solid #fff;margin-bottom:-2px}

.tab-pane{display:none;padding:28px 40px 40px}
.tab-pane.active{display:block}

/* Summary */
.summary{display:flex;gap:20px;margin-bottom:24px;flex-wrap:wrap}
.summary-box{background:#fff;border-radius:10px;padding:12px 20px;
  box-shadow:0 1px 5px rgba(0,0,0,.07);display:flex;flex-direction:column;gap:2px}
.summary-box .s-num{font-size:26px;font-weight:700}
.summary-box .s-lbl{font-size:12px;color:#777}
.s-green{color:#1a6630}.s-red{color:#8a1500}.s-blue{color:#1a4080}

/* Theory tables section */
.theory-section{background:#fff;border-radius:12px;padding:24px 28px;
  margin-bottom:28px;box-shadow:0 1px 6px rgba(0,0,0,.08)}
.theory-title{font-size:16px;font-weight:700;color:#12122a;
  margin:20px 0 10px;padding-bottom:6px;border-bottom:2px solid #e8eaee}
.theory-title:first-child{margin-top:0}
.theory-note{font-size:13px;color:#666;margin-bottom:10px;line-height:1.6}
.tbl-scroll{overflow-x:auto}

/* theory-tbl (shared by all theory tables) */
.theory-tbl{border-collapse:collapse;font-size:13px;width:100%;margin-bottom:4px}
.theory-tbl th{background:#f2f4f7;padding:7px 12px;text-align:left;
  font-weight:700;color:#444;border:1px solid #dde;white-space:nowrap}
.theory-tbl td{padding:6px 12px;border:1px solid #e8eaee;vertical-align:top}
.theory-tbl .empty-cell{color:#ccc;background:#fafafa}
.theory-tbl .ll1-entry{font-size:12px}
.theory-tbl .top-border td{border-top:2px solid #ccd}

.nt{font-weight:700;color:#1a3a7a;font-family:"Courier New",monospace}
.prod{color:#333;font-family:"Courier New",monospace}
.term{background:#f0f0f0;padding:1px 5px;border-radius:3px;color:#8a1500;font-size:12px}
.eps{font-style:italic;color:#777}
.pipe{color:#999}
.set-cell{font-size:12px}

/* Shift/Reduce action cells */
.sr-shift{background:#e8f5e9;color:#1a6630;font-weight:700;text-align:center}
.sr-reduce{background:#fdeaea;color:#8a1500;font-weight:700;text-align:center}
.sr-shift-tag{background:#1a6630;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px}
.sr-reduce-tag{background:#8a1500;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px}
.tbl-note{font-size:12px;color:#666;margin-top:8px}

/* Case cards */
.section-cases-title{font-size:18px;font-weight:700;color:#333;margin:24px 0 12px}
.case-card{background:#fff;border-radius:12px;margin-bottom:20px;
  box-shadow:0 1px 6px rgba(0,0,0,.08);overflow:hidden}
.case-header{display:flex;align-items:center;gap:12px;padding:14px 20px;
  background:#f8f9fb;border-bottom:1px solid #e8eaee;flex-wrap:wrap}
.case-num{font-size:12px;font-weight:700;color:#999;min-width:28px}
.case-desc{font-size:14px;font-weight:600;color:#333;flex:1;min-width:160px}
.case-src{background:#f0f0f0;color:#c0392b;padding:3px 10px;border-radius:5px;
  font-size:13px;max-width:360px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.badge{font-size:11px;font-weight:700;letter-spacing:.5px;
  padding:3px 10px;border-radius:20px;white-space:nowrap}
.badge-pass{background:#d4edda;color:#1a6630}
.badge-lex{background:#fce8d5;color:#8a3500}
.badge-par{background:#fde8e8;color:#8a1500}
.badge-sem{background:#fdf3d5;color:#7a5000}

.phases{padding:0 20px 18px}
.phase-block{margin-top:16px}
.ph-header{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-radius:6px;font-size:13px;font-weight:600;margin-bottom:10px}
.ph-pass{background:#edfaef;color:#1a6630}
.ph-fail{background:#fdeaea;color:#8a1500}
.ph-skip{background:#f2f2f2;color:#888}
.ph-icon{font-size:15px;width:20px;text-align:center}
.ph-num{opacity:.7}
.ph-title{flex:1}
.ph-body{padding:0 8px}
.ph-stat{font-size:13px;color:#555;margin-bottom:8px}
.ph3-sub{font-size:12px;font-weight:600;color:#555;
  text-transform:uppercase;letter-spacing:.5px;margin:12px 0 6px}

/* Token table */
.tok-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:4px}
.tok-tbl th{background:#f2f4f7;text-align:left;padding:5px 10px;
  font-weight:600;color:#555;border-bottom:1px solid #dde}
.tok-tbl td{padding:4px 10px;border-bottom:1px solid #f0f0f0}
.tok-tbl .tt{color:#1a5276;font-weight:600;font-size:12px}

/* Symbol table */
.sym-tbl{border-collapse:collapse;font-size:13px;margin-bottom:12px;width:auto}
.sym-tbl th{background:#f2f4f7;padding:6px 16px;border-bottom:1px solid #dde;
  color:#555;font-weight:600}
.sym-tbl td{padding:5px 16px;border-bottom:1px solid #f0f0f0}

.print-list{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.print-list li{background:#f5f5f5;border-radius:4px;padding:4px 10px;font-size:13px}

/* AST visual */
.ast-row{display:flex;flex-wrap:wrap;gap:20px;margin-bottom:12px}
.ast-item{display:flex;flex-direction:column;gap:6px}
.ast-item-label{font-size:12px;color:#666}
.ast-item-label code{background:#f0f0f0;padding:1px 6px;border-radius:3px;color:#c0392b}
.text-ast{background:#f8f9fb;border:1px solid #e4e6ea;border-radius:6px;
  padding:10px 14px;font-size:13px;font-family:"Courier New",monospace;
  color:#333;overflow-x:auto;line-height:1.6;margin-top:4px}

/* Parse steps */
.steps-details{margin-top:10px}

/* Error display with source context */
.error-formatted{background:#fdeaea;border-left:3px solid #8a1500;padding:10px 12px;
  margin:8px 0;border-radius:4px;font-size:13px;color:#333}
.error-msg-line{color:#8a1500;font-weight:600;margin-bottom:8px}
.error-source-code{background:#f5f5f5;border:1px solid #ddd;border-radius:3px;
  padding:8px 10px;margin:6px 0;font-family:'Courier New',monospace;font-size:12px;
  color:#333;overflow-x:auto;line-height:1.5;white-space:pre}
.error-caret-line{color:#8a1500;font-weight:bold;font-family:'Courier New',monospace;
  font-size:12px;margin:2px 0 0;white-space:pre;padding:0 10px}
.steps-details summary{font-size:13px;color:#555;cursor:pointer;padding:6px 10px;
  background:#f5f5f5;border-radius:5px;user-select:none}
.step-list{list-style:none;padding:0;margin-top:6px;
  font-family:"Courier New",monospace;font-size:12px;max-height:320px;overflow-y:auto;
  border:1px solid #e8eaee;border-radius:6px}
.step-list li{padding:4px 12px;border-bottom:1px solid #f0f0f0;line-height:1.5}
.step-shift{background:#f0f7ff;color:#1a3a7a}
.step-reduce{background:#fff8f0;color:#7a3a00}
.step-accept{background:#edfaef;color:#1a6630;font-weight:700}
.step-sep{background:#f5f5f5;color:#888;font-style:italic}
.step-other{color:#444}

.err-msg{background:#fff5f5;border-left:3px solid #e74c3c;color:#8a1500;
  font-family:monospace;font-size:13px;padding:10px 14px;
  border-radius:0 6px 6px 0;white-space:pre-wrap}
.empty{font-size:13px;color:#aaa;font-style:italic}
"""

_JS = """
function showTab(id, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}
"""


# ── Public API ────────────────────────────────────────────────

def generate_report(test_cases: list[tuple[str, str]], out_path: Path, parsers: str = "both") -> Path:
    """
    Generate HTML report for test cases.
    
    Parameters:
    -----------
    test_cases : list of (description, source) tuples
    out_path   : Path to write HTML to
    parsers    : "top-down", "bottom-up", or "both" (default)
    """
    # Run parsers based on selection
    if parsers in ("top-down", "both"):
        td_results = [_run(i+1, d, s, False) for i, (d, s) in enumerate(test_cases)]
    else:
        td_results = None
    
    if parsers in ("bottom-up", "both"):
        bu_results = [_run(i+1, d, s, True)  for i, (d, s) in enumerate(test_cases)]
    else:
        bu_results = None

    # Generate tab sections only for selected parsers
    tab_buttons = ""
    tab_panes = ""
    
    if td_results is not None:
        td_html = _section_html(td_results, is_top_down=True)
        tab_buttons += '  <button class="tab-btn active" onclick="showTab(\'tab-td\', this)">\n'
        tab_buttons += '    Top-Down Parser &nbsp;(Recursive Descent, LL(1))\n'
        tab_buttons += '  </button>\n'
        tab_panes += f'<div id="tab-td" class="tab-pane active">{td_html}</div>\n'
    
    if bu_results is not None:
        bu_html = _section_html(bu_results, is_top_down=False)
        active_class = " active" if td_results is None else ""
        tab_buttons += '  <button class="tab-btn' + active_class + '" onclick="showTab(\'tab-bu\', this)">\n'
        tab_buttons += '    Bottom-Up Parser &nbsp;(Shift-Reduce, Operator-Precedence)\n'
        tab_buttons += '  </button>\n'
        tab_panes += f'<div id="tab-bu" class="tab-pane{active_class}">{bu_html}</div>\n'

    # Determine summary text
    parser_text = "both parsers" if parsers == "both" else f"{parsers} parser"

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Front-End Compiler -- Full Report</title>
<style>{_CSS}</style>
</head>
<body>

<div class="banner">
  <h1>Front-End Compiler &mdash; Full Report</h1>
  <div class="sub">
    {len(test_cases)} test cases &bull; {parser_text} &bull;
    all three phases &bull; grammar tables &bull; parse steps &bull; symbol table
  </div>
</div>

<div class="re-bar">
  <div>RE1 (numbers) &nbsp;<span>{_e(RE1_NUMBER)}</span></div>
  <div>RE2 (identifiers) &nbsp;<span>{_e(RE2_IDENTIFIER)}</span></div>
  <div>RE3 (operators) &nbsp;<span>{_e(RE3_OPERATOR)}</span></div>
  <div>Master &nbsp;<span>RE1 | RE2 | COMMENT | RE3 | WHITESPACE | INVALID</span></div>
</div>

<div class="tab-bar">
{tab_buttons}</div>

{tab_panes}
<script>{_JS}</script>
</body>
</html>"""

    out_path.write_text(page, encoding="utf-8")
    return out_path
