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

# ── Original grammar (WITH left recursion) ──────────────────
# This is the NATURAL expression grammar that encodes precedence
# directly. It CANNOT be used by a top-down (LL) parser because
# the rules E → E + T and T → T * F are left-recursive, which
# would cause infinite recursion in recursive descent parsing.
#
# ORIGINAL (left-recursive):
#   E → E + T | E - T | T
#   T → T * F | T / F | F
#   F → ( E ) | id | num
#
# This grammar correctly captures that:
#   • * and / bind tighter than + and - (T is "inside" E)
#   • All operators are left-associative (E appears on the LEFT)
#
# ── After left-recursion elimination ────────────────────────
# To make this grammar LL(1) compatible, we eliminate left
# recursion using the standard transformation:
#
#   A → A α | β    becomes    A → β A'
#                              A' → α A' | eps
#
# Applying to E → E + T | E - T | T:
#   α₁ = + T,  α₂ = - T,  β = T
#   E  → T E'
#   E' → + T E' | - T E' | eps
#
# Applying to T → T * F | T / F | F:
#   α₁ = * F,  α₂ = / F,  β = F
#   T  → F T'
#   T' → * F T' | / F T' | eps

# Display form: left-recursion-free expression grammar with unary operators
FULL_GRAMMAR = [
    ("E",   "T  E'"),
    ("E'",  "'+'  T  E'   |   '-'  T  E'   |   eps"),
    ("T",   "F  T'"),
    ("T'",  "'*'  F  T'   |   '/'  F  T'   |   eps"),
    ("F",   "'+'  F   |   '-'  F   |   '('  E  ')'   |   id   |   num"),
]

# For HTML reports: original grammar (for comparison)
ORIGINAL_GRAMMAR = [
    ("E",   "E  '+'  T   |   E  '-'  T   |   T"),
    ("T",   "T  '*'  F   |   T  '/'  F   |   F"),
    ("F",   "'+'  F   |   '-'  F   |   '('  E  ')'   |   id   |   num"),
]

# Expression sub-grammar in machine-readable form (for FIRST/FOLLOW/LL(1))
# This is the LEFT-RECURSION-FREE version used by the LL(1) parser
# Updated to include unary operators in F
_NT  = ["E", "E'", "T", "T'", "F"]
_T   = ["+", "-", "*", "/", "(", ")", "id", "num", "$"]
_SYM = set(_NT)

EXPR_GRAMMAR: dict[str, list[list[str]]] = {
    "E":  [["T",  "E'"]],
    "E'": [["+",  "T",  "E'"],
           ["-",  "T",  "E'"],
           ["eps"]],
    "T":  [["F",  "T'"]],
    "T'": [["*",  "F",  "T'"],
           ["/",  "F",  "T'"],
           ["eps"]],
    "F":  [["+", "F"],
           ["-", "F"],
           ["(", "E", ")"],
           ["id"],
           ["num"]],
}

_EPSILON = "eps"
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
                   start: str = "E") -> dict[str, set[str]]:
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


def analyze_expression_tokens(source_tokens: list) -> list[dict]:
    """Analyze how FIRST/FOLLOW sets apply to each token in a specific expression.
    
    Returns a list of dicts, one per token, showing:
    - The token value and type
    - Which non-terminals have this token in their FIRST set
    - Which non-terminals have this token in their FOLLOW set
    - What grammar rule applies when this token is the lookahead
    """
    from compiler.tokens import TokenType
    
    # Map token types to grammar terminals
    token_to_terminal = {
        TokenType.NUMBER: "num",
        TokenType.IDENTIFIER: "id",
        TokenType.PLUS: "+",
        TokenType.MINUS: "-",
        TokenType.MULTIPLY: "*",
        TokenType.DIVIDE: "/",
        TokenType.LPAREN: "(",
        TokenType.RPAREN: ")",
        TokenType.EOF: "$",
    }
    
    # Pre-compute FIRST and FOLLOW for the grammar
    first = compute_first(EXPR_GRAMMAR)
    follow = compute_follow(EXPR_GRAMMAR, first)
    
    analysis = []
    for tok in source_tokens:
        if tok.type == TokenType.EOF:
            continue
            
        terminal = token_to_terminal.get(tok.type)
        if not terminal:
            continue
        
        # Find which non-terminals have this terminal in their FIRST set
        first_of = [nt for nt in _NT if terminal in first.get(nt, set())]
        
        # Find which non-terminals have this terminal in their FOLLOW set  
        follow_of = [nt for nt in _NT if terminal in follow.get(nt, set())]
        
        # Determine which production would be chosen if this is the lookahead
        productions_used = []
        for nt in _NT:
            if terminal in first.get(nt, set()):
                # This non-terminal could derive a string starting with this token
                for prod in EXPR_GRAMMAR[nt]:
                    prod_first = _production_first(prod, first)
                    if terminal in prod_first:
                        productions_used.append((nt, prod))
                        break
            elif terminal in follow.get(nt, set()):
                # This non-terminal could be followed by this token (epsilon case)
                if ["ε"] in EXPR_GRAMMAR[nt]:
                    productions_used.append((nt, ["ε"]))
        
        analysis.append({
            "token": tok.value,
            "token_type": tok.type.name,
            "terminal": terminal,
            "first_of": first_of,
            "follow_of": follow_of,
            "productions": productions_used,
        })
    
    return analysis


def _production_first(prod: list[str], first: dict) -> set[str]:
    """Compute FIRST of a production string (sequence of symbols)."""
    result: set[str] = set()
    for sym in prod:
        f = first.get(sym, {sym})
        result.update(f - {_EPSILON})
        if _EPSILON not in f:
            return result
    result.add(_EPSILON)
    return result


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
    """Full language grammar as an HTML table (transformed, LL(1) version)."""
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


def render_original_grammar_html() -> str:
    """Original left-recursive grammar (before transformation).
    
    Shows the natural expression grammar that encodes precedence and
    associativity, but cannot be used by LL(1) parsers due to left recursion.
    """
    rows = [
        f'<thead><tr>'
        f'{_th("Non-terminal")}'
        f'{_th("Production")}'
        f'{_th("Note")}'
        f'</tr></thead><tbody>'
    ]
    
    notes = {
        "E": "Left-recursive!",
        "T": "Left-recursive!",
        "F": "",
    }
    
    seen: set[str] = set()
    for lhs, rhs in ORIGINAL_GRAMMAR:
        lhs_cell = f'<span class="nt">{lhs}</span>' if lhs not in seen else ""
        seen.add(lhs)
        note = notes.get(lhs, "")
        note_cell = f'<span class="warning-note">{note}</span>' if note else ""
        rows.append(
            f'<tr>{_td(lhs_cell)}'
            f'{_td("&rarr; &nbsp;" + _fmt_prod(rhs))}'
            f'{_td(note_cell)}</tr>'
        )
    rows.append("</tbody>")
    
    caption = (
        '<caption>Original Grammar (with left recursion — cannot be parsed top-down)</caption>'
    )
    return _table(rows).replace('<table', f'<table').replace('><thead', f'>{caption}<thead')


def render_first_follow_html() -> str:
    """FIRST and FOLLOW sets as an HTML table."""
    rule_rows = [
        ("E",   "T  E'",          _first_str("E"),   _FOLLOW["E"]),
        ("E'",  "+ T E'",         {"+"},              _FOLLOW["E'"]),
        ("E'",  "- T E'",         {"-"},              _FOLLOW["E'"]),
        ("E'",  "eps",            {_EPSILON},         _FOLLOW["E'"]),
        ("T",   "F  T'",          _first_str("T"),   _FOLLOW["T"]),
        ("T'",  "* F T'",         {"*"},              _FOLLOW["T'"]),
        ("T'",  "/ F T'",         {"/"},              _FOLLOW["T'"]),
        ("T'",  "eps",            {_EPSILON},         _FOLLOW["T'"]),
        ("F",   "( E )",          {"("},              _FOLLOW["F"]),
        ("F",   "id",             {"id"},             _FOLLOW["F"]),
        ("F",   "num",            {"num"},            _FOLLOW["F"]),
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


def render_dynamic_sr_table_html(decisions: list[dict]) -> str:
    """Dynamic shift-reduce decision table based on actual parsing trace.
    
    Shows only the operators and decisions that occurred for the specific expression.
    """
    if not decisions:
        return '<p class="tbl-note">No shift-reduce decisions recorded.</p>'
    
    # Extract unique operators that appeared
    ops_used: set[str] = set()
    for d in decisions:
        if d.get("stack_op"):
            ops_used.add(d["stack_op"])
        # Also check lookahead for operators
        look = d.get("lookahead", "")
        if look in ("+", "-", "*", "/"):
            ops_used.add(look)
    
    # Build the dynamic precedence sub-table for operators actually used
    ops_sorted = sorted(ops_used, key=lambda op: _PREC.get(op, 0))
    
    rows = [
        f'<thead><tr>'
        f'{_th("Stack op \\ Lookahead")}'
        f'{"".join(_th(t) for t in ops_sorted + [")", "$"])}'
        f'</tr></thead><tbody>'
    ]
    
    for op in ops_sorted:
        cells = _td(f'<span class="nt">{op}</span> (prec={_PREC[op]})')
        for look in ops_sorted + [")", "$"]:
            action = _sr_action(op, look)
            cls    = "sr-shift" if action == "S" else "sr-reduce"
            cells += _td(action, cls)
        rows.append(f'<tr>{cells}</tr>')
    
    rows.append("</tbody>")
    
    # Add a legend showing the actual decisions made during parsing
    decision_rows: list[str] = []
    step_num = 0
    for d in decisions:
        if d["type"] == "PRECISION_CHECK":
            step_num += 1
            stack_op_html = '<span class="nt">' + d["stack_op"] + '</span>'
            lookahead_html = '<code>' + d["lookahead"] + '</code>'
            decision_html = '<span class="sr-reduce">REDUCE</span>'
            decision_rows.append(
                f'<tr>'
                f'{_td(str(step_num), "step-num")}'
                f'{_td(stack_op_html)}'
                f'{_td(lookahead_html)}'
                f'{_td(decision_html)}'
                f'{_td(d["reason"], "reason-cell")}'
                f'</tr>'
            )
        elif d["type"] == "SHIFT":
            step_num += 1
            stack_op_val = d.get("stack_op", "&mdash;") or "&mdash;"
            lookahead_html = '<code>' + d["lookahead"] + '</code>'
            decision_html = '<span class="sr-shift">SHIFT</span>'
            decision_rows.append(
                f'<tr>'
                f'{_td(str(step_num), "step-num")}'
                f'{_td(stack_op_val)}'
                f'{_td(lookahead_html)}'
                f'{_td(decision_html)}'
                f'{_td(d["reason"], "reason-cell")}'
                f'</tr>'
            )
    
    decision_table = ""
    if decision_rows:
        decision_table = (
            '<h4 class="sub-section-title">Parsing Trace (Decisions Made)</h4>'
            '<table class="sr-trace-table">'
            '<thead><tr>'
            f'{_th("Step")}'
            f'{_th("Stack Op")}'
            f'{_th("Lookahead")}'
            f'{_th("Decision")}'
            f'{_th("Reason")}'
            '</tr></thead><tbody>'
            + "\n".join(decision_rows)
            + '</tbody></table>'
        )
    
    legend = (
        '<p class="tbl-note">'
        '<span class="sr-shift-tag">S</span> = Shift &nbsp;'
        '(lookahead binds tighter) &nbsp;|&nbsp; '
        '<span class="sr-reduce-tag">R</span> = Reduce &nbsp;'
        '(stack operator has equal or higher precedence)'
        '</p>'
    )
    
    return _table(rows) + legend + decision_table


def render_ll1_trace_html(decisions: list[dict]) -> str:
    """Dynamic LL(1) parsing trace showing actual table lookups for the expression.
    
    Shows how the LL(1) parsing table M[A, a] was consulted at each step.
    """
    if not decisions:
        return '<p class="tbl-note">No LL(1) decisions recorded.</p>'
    
    rows = []
    step_num = 0
    
    for d in decisions:
        step_num += 1
        # Highlight epsilon productions
        is_epsilon = "eps" in d["production"].lower() or d["production"] == "EOF"
        row_class = "epsilon-row" if is_epsilon else ""
        
        nonterminal_html = '<span class="nt">' + d["nonterminal"] + '</span>'
        lookahead_html = '<code>' + d["lookahead"] + '</code>'
        
        rows.append(
            f'<tr class="{row_class}">'
            f'{_td(str(step_num), "step-num")}'
            f'{_td(nonterminal_html)}'
            f'{_td(lookahead_html)}'
            f'{_td(d["production"])}'
            f'{_td(d["reason"], "reason-cell")}'
            f'</tr>'
        )
    
    table_html = (
        '<table class="ll1-trace-table">'
        '<thead><tr>'
        f'{_th("Step")}'
        f'{_th("Non-terminal")}'
        f'{_th("Lookahead")}'
        f'{_th("Production Used")}'
        f'{_th("LL(1) Table Lookup Reason")}'
        '</tr></thead><tbody>'
        + "\n".join(rows)
        + '</tbody></table>'
    )
    
    note = (
        '<p class="tbl-note">'
        'Each row shows one consultation of the LL(1) parsing table M[A, a]. '
        'The parser looks at the current non-terminal (row) and lookahead token (column), '
        'then selects the production at that table entry. '
        'Epsilon (eps) productions mean "match nothing" — the loop terminates.'
        '</p>'
    )
    
    return table_html + note


def render_token_first_follow_html(token_analysis: list[dict]) -> str:
    """Show FIRST/FOLLOW sets for each token in the specific expression.
    
    For an expression like "4 * 8 / 3", this shows:
    - Token "4": FIRST(E)={num,id,(}, FIRST(T)={num,id,(}, FIRST(F)={num,id,(}
    - Token "*": In FIRST(T')={*,/}, triggers T' → '*' F T'
    - etc.
    """
    if not token_analysis:
        return '<p class="tbl-note">No token analysis available.</p>'
    
    rows = []
    for i, tok_info in enumerate(token_analysis, 1):
        # Build FIRST set display for this token
        first_html_parts = []
        for nt in tok_info["first_of"]:
            first_html_parts.append(f'<span class="nt">{nt}</span>')
        first_display = ', '.join(first_html_parts) if first_html_parts else '<span class="none">—</span>'
        
        # Build FOLLOW set display
        follow_html_parts = []
        for nt in tok_info["follow_of"]:
            follow_html_parts.append(f'<span class="nt">{nt}</span>')
        follow_display = ', '.join(follow_html_parts) if follow_html_parts else '<span class="none">—</span>'
        
        # Build productions display
        prod_html_parts = []
        for nt, prod in tok_info["productions"]:
            prod_str = ' '.join(prod)
            prod_html_parts.append(
                f'<span class="nt">{nt}</span> → <code>{_fmt_prod(prod_str)}</code>'
            )
        prod_display = '<br>'.join(prod_html_parts) if prod_html_parts else '<span class="none">—</span>'
        
        token_html = '<code class="token-val">' + tok_info["token"] + '</code>'
        type_html = '<span class="token-type">' + tok_info["token_type"] + '</span>'
        
        rows.append(
            f'<tr>'
            f'{_td(str(i), "step-num")}'
            f'{_td(token_html)}'
            f'{_td(type_html)}'
            f'{_td(first_display)}'
            f'{_td(follow_display)}'
            f'{_td(prod_display, "prod-cell")}'
            f'</tr>'
        )
    
    table_html = (
        '<table class="token-first-follow-table">'
        '<thead><tr>'
        f'{_th("Position")}'
        f'{_th("Token")}'
        f'{_th("Type")}'
        f'{_th("In FIRST of")}'
        f'{_th("In FOLLOW of")}'
        f'{_th("Production Triggered")}'
        '</tr></thead><tbody>'
        + "\n".join(rows)
        + '</tbody></table>'
    )
    
    note = (
        '<p class="tbl-note">'
        'For each token in the expression, this table shows which non-terminals have this token '
        'in their FIRST set (can derive strings starting with this token) and '
        'FOLLOW set (can be followed by this token). '
        'The "Production Triggered" column shows which grammar rule fires when this token is the lookahead.'
        '</p>'
    )
    
    return table_html + note


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
