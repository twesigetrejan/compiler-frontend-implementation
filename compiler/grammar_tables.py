# -*- coding: utf-8 -*-
# compiler/grammar_tables.py
# ─────────────────────────────────────────────────────────────
# Theory tables for the HTML report:
#   1. Grammar display (full language grammar)
#   2. FIRST and FOLLOW sets (expression sub-grammar, LL(1))
#   3. LL(1) Predictive Parsing Table  M[A, a]
#   4. Operator-Precedence Table       (shift-reduce parser)
#
# All public functions return self-contained HTML strings.
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

# ══════════════════════════════════════════════════════════════
# 1. GRAMMAR DEFINITION
# ══════════════════════════════════════════════════════════════

# Full language grammar (display form)
FULL_GRAMMAR = [
    ("program",  "stmt  program   |  ε"),
    ("stmt",     "id  '='  expr  ';'"),
    ("stmt",     "'print'  '('  expr  ')'  ';'"),
    ("stmt",     "expr  ';'"),
    ("expr",     "term  expr'"),
    ("expr'",    "'+'  term  expr'   |   '-'  term  expr'   |   ε"),
    ("term",     "factor  term'"),
    ("term'",    "'*'  factor  term'   |   '/'  factor  term'   |   ε"),
    ("factor",   "'('  expr  ')'   |   id   |   num"),
]

# Expression sub-grammar — uses full names matching the parser code
_NT  = ["expr", "expr'", "term", "term'", "factor"]
_T   = ["+", "-", "*", "/", "(", ")", "id", "num", "$"]
_SYM = set(_NT)

EXPR_GRAMMAR: dict[str, list[list[str]]] = {
    "expr":   [["term",   "expr'"]],
    "expr'":  [["+",      "term",   "expr'"],
               ["-",      "term",   "expr'"],
               ["ε"]],
    "term":   [["factor", "term'"]],
    "term'":  [["*",      "factor", "term'"],
               ["/",      "factor", "term'"],
               ["ε"]],
    "factor": [["(", "expr", ")"],
               ["id"],
               ["num"]],
}

_EPSILON = "ε"
_EOF     = "$"


# ══════════════════════════════════════════════════════════════
# 2. FIRST and FOLLOW  computation
# ══════════════════════════════════════════════════════════════

def compute_first(grammar: dict) -> dict[str, set[str]]:
    """Compute FIRST sets for all symbols in grammar."""
    first: dict[str, set[str]] = {}

    for nt in _NT:
        first[nt] = set()
    for t in _T:
        first[t] = {t}
    first[_EPSILON] = {_EPSILON}

    changed = True
    while changed:
        changed = False
        for nt, prods in grammar.items():
            for prod in prods:
                i = 0
                while i < len(prod):
                    sym = prod[i]
                    before = len(first[nt])
                    first[nt].update(first.get(sym, {sym}) - {_EPSILON})
                    if _EPSILON not in first.get(sym, set()):
                        break
                    i += 1
                else:
                    if _EPSILON not in first[nt]:
                        first[nt].add(_EPSILON)
                        changed = True
                if len(first[nt]) > before:
                    changed = True
    return first


def compute_follow(grammar: dict, first: dict[str, set[str]],
                   start: str = "expr") -> dict[str, set[str]]:
    """Compute FOLLOW sets for all non-terminals."""
    follow: dict[str, set[str]] = {nt: set() for nt in _NT}
    follow[start].add(_EOF)

    changed = True
    while changed:
        changed = False
        for lhs, prods in grammar.items():
            for prod in prods:
                trailer = follow[lhs].copy()
                for sym in reversed(prod):
                    if sym in _SYM:
                        before = len(follow[sym])
                        follow[sym].update(trailer)
                        if _EPSILON in first.get(sym, set()):
                            trailer = trailer | (first[sym] - {_EPSILON})
                        else:
                            trailer = first.get(sym, {sym})
                        if len(follow[sym]) > before:
                            changed = True
                    else:
                        trailer = first.get(sym, {sym})
    return follow


# ══════════════════════════════════════════════════════════════
# 3. LL(1) PREDICTIVE PARSING TABLE  M[A, a]
# ══════════════════════════════════════════════════════════════

def build_ll1_table(grammar: dict,
                    first: dict[str, set[str]],
                    follow: dict[str, set[str]]
                    ) -> dict[tuple[str, str], list[str]]:
    table: dict[tuple[str, str], list[str]] = {}

    def first_of_string(symbols: list[str]) -> set[str]:
        result: set[str] = set()
        for sym in symbols:
            f = first.get(sym, {sym})
            result.update(f - {_EPSILON})
            if _EPSILON not in f:
                return result
        result.add(_EPSILON)
        return result

    for nt, prods in grammar.items():
        for prod in prods:
            first_alpha = first_of_string(prod)
            for terminal in first_alpha:
                if terminal != _EPSILON:
                    table[(nt, terminal)] = prod
            if _EPSILON in first_alpha:
                for terminal in follow[nt]:
                    table[(nt, terminal)] = prod

    return table


# Pre-compute once
_FIRST  = compute_first(EXPR_GRAMMAR)
_FOLLOW = compute_follow(EXPR_GRAMMAR, _FIRST)
_LL1    = build_ll1_table(EXPR_GRAMMAR, _FIRST, _FOLLOW)


# ══════════════════════════════════════════════════════════════
# 4. OPERATOR-PRECEDENCE TABLE  (shift-reduce parser)
# ══════════════════════════════════════════════════════════════

_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}
_OPS  = ["+", "-", "*", "/"]
_LOOK = ["+", "-", "*", "/", ")", "$"]


def _sr_action(stack_op: str, look: str) -> str:
    sp = _PREC.get(stack_op, 0)
    lp = _PREC.get(look, 0)
    if look in (")", "$"):
        return "R"
    return "R" if sp >= lp else "S"


# ══════════════════════════════════════════════════════════════
# HTML HELPERS
# ══════════════════════════════════════════════════════════════

def _th(text: str) -> str:
    return f'<th>{text}</th>'

def _td(text: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f'<td{attr}>{text}</td>'

def _table(rows: list[str], caption: str = "") -> str:
    cap = f'<caption>{caption}</caption>' if caption else ""
    body = "\n".join(rows)
    return f'<table class="theory-tbl">{cap}{body}</table>'


# ══════════════════════════════════════════════════════════════
# PUBLIC RENDERERS
# ══════════════════════════════════════════════════════════════

def render_grammar_html() -> str:
    """Full language grammar as an HTML table."""
    rows = [f'<thead><tr>{_th("Non-terminal")}{_th("Production")}</tr></thead><tbody>']
    seen: set[str] = set()
    for lhs, rhs in FULL_GRAMMAR:
        lhs_cell = f'<span class="nt">{lhs}</span>' if lhs not in seen else ""
        seen.add(lhs)
        rows.append(
            f'<tr>{_td(lhs_cell)}'
            f'{_td("&rarr; &nbsp;" + _fmt_prod(rhs))}</tr>'
        )
    rows.append("</tbody>")
    return _table(rows)


def render_first_follow_html() -> str:
    """FIRST and FOLLOW sets as an HTML table."""
    rule_rows = [
        ("expr",   "term  expr'",      _first_str("expr"),   _FOLLOW["expr"]),
        ("expr'",  "+ term expr'",     {"+"},                 _FOLLOW["expr'"]),
        ("expr'",  "- term expr'",     {"-"},                 _FOLLOW["expr'"]),
        ("expr'",  "ε",               {_EPSILON},             _FOLLOW["expr'"]),
        ("term",   "factor  term'",   _first_str("term"),    _FOLLOW["term"]),
        ("term'",  "* factor term'",  {"*"},                  _FOLLOW["term'"]),
        ("term'",  "/ factor term'",  {"/"},                  _FOLLOW["term'"]),
        ("term'",  "ε",               {_EPSILON},             _FOLLOW["term'"]),
        ("factor", "( expr )",        {"("},                  _FOLLOW["factor"]),
        ("factor", "id",              {"id"},                 _FOLLOW["factor"]),
        ("factor", "num",             {"num"},                _FOLLOW["factor"]),
    ]

    rows = [
        f'<thead><tr>'
        f'{_th("A &rarr; &alpha;")}'
        f'{_th("FIRST(&alpha;)")}'
        f'{_th("FOLLOW(A)")}'
        f'</tr></thead><tbody>'
    ]
    prev_lhs = None
    for lhs, rhs, first_a, follow_a in rule_rows:
        lhs_cell = (
            f'<span class="nt">{lhs}</span> &rarr; '
            f'<span class="prod">{_fmt_prod(rhs)}</span>'
        )
        border_cls = "top-border" if lhs != prev_lhs else ""
        rows.append(
            f'<tr class="{border_cls}">'
            f'{_td(lhs_cell)}'
            f'{_td(_set_str(first_a),  "set-cell")}'
            f'{_td(_set_str(follow_a), "set-cell")}'
            f'</tr>'
        )
        prev_lhs = lhs
    rows.append("</tbody>")
    return _table(rows)


def render_ll1_table_html() -> str:
    """LL(1) predictive parsing table M[A, a]."""
    terminals_display = ["+", "-", "*", "/", "(", ")", "id", "num", "$"]
    header_cells = "".join(_th(t) for t in terminals_display)
    rows = [f'<thead><tr>{_th("")}{header_cells}</tr></thead><tbody>']

    for nt in _NT:
        cells = _td(f'<span class="nt">{nt}</span>')
        for term in terminals_display:
            prod = _LL1.get((nt, term))
            if prod is None:
                cells += _td("", "empty-cell")
            else:
                rhs = " ".join(prod)
                cells += _td(
                    f'<span class="nt">{nt}</span> &rarr; '
                    f'<span class="prod">{_fmt_prod(rhs)}</span>',
                    "ll1-entry"
                )
        rows.append(f'<tr>{cells}</tr>')

    rows.append("</tbody>")
    return _table(rows)


def render_precedence_table_html() -> str:
    """Operator-Precedence table for the shift-reduce parser."""
    col_header = _th("Stack op \\ Lookahead")
    header_cells = "".join(_th(t) for t in _LOOK)
    rows = [
        f'<thead><tr>'
        f'{col_header}'
        f'{header_cells}'
        f'</tr></thead><tbody>'
    ]
    for op in _OPS:
        cells = _td(f'<span class="nt">{op}</span> (prec={_PREC[op]})')
        for look in _LOOK:
            action = _sr_action(op, look)
            cls    = "sr-shift" if action == "S" else "sr-reduce"
            cells += _td(action, cls)
        rows.append(f'<tr>{cells}</tr>')
    rows.append("</tbody>")

    legend = (
        '<p class="tbl-note">'
        '<span class="sr-shift-tag">S</span> = Shift &nbsp;'
        '(lookahead binds tighter) &nbsp;|&nbsp; '
        '<span class="sr-reduce-tag">R</span> = Reduce &nbsp;'
        '(stack operator has equal or higher precedence)'
        '</p>'
    )
    return _table(rows) + legend


def render_reduce_rules_html() -> str:
    """Grammar rules used as reductions in the shift-reduce parser."""
    rules = [
        ("NUMBER  &rarr;  EXPR",              "A numeric literal becomes an expression"),
        ("IDENTIFIER  &rarr;  EXPR",          "A variable reference becomes an expression"),
        ("EXPR op EXPR  &rarr;  EXPR",        "Two exprs joined by +  &minus;  *  / collapse into one"),
        ("( EXPR )  &rarr;  EXPR",            "Parenthesised expression unwraps"),
        ("EXPR ;  &rarr;  STMT",              "An expression followed by ; becomes a statement"),
        ("id = EXPR  &rarr;  STMT",           "Assignment becomes a statement"),
        ("print ( EXPR )  &rarr;  STMT",      "Print call becomes a statement"),
    ]
    rows = [
        f'<thead><tr>{_th("Reduce rule")}{_th("When applied")}</tr></thead><tbody>'
    ]
    for rule, note in rules:
        rows.append(
            f'<tr>{_td(f"<code>{rule}</code>")}{_td(note)}</tr>'
        )
    rows.append("</tbody>")
    return _table(rows)


# ══════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════

def _fmt_prod(rhs: str) -> str:
    out: list[str] = []
    for tok in rhs.split():
        if tok == "|":
            out.append('<span class="pipe"> | </span>')
        elif tok == _EPSILON:
            out.append('<span class="eps">&epsilon;</span>')
        elif tok in _SYM:
            out.append(f'<span class="nt">{tok}</span>')
        else:
            out.append(f'<code class="term">{tok}</code>')
    return " ".join(out)


def _first_str(nt: str) -> set[str]:
    return _FIRST.get(nt, set())


def _set_str(s: set[str]) -> str:
    """Format a set for display, ε last, sorted."""
    items = sorted(s - {_EPSILON}) + ([_EPSILON] if _EPSILON in s else [])
    parts = []
    for x in items:
        if x == _EPSILON:
            parts.append('<span class="eps">&epsilon;</span>')
        else:
            parts.append(f'<code>{x}</code>')
    return "{ " + ",  ".join(parts) + " }"
