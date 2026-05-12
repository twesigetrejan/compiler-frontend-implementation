# Front-End Compiler — Commands & Walkthrough

## Quick Reference — All Commands

```bash
# Run all 64 unit tests (recommended first step)
python -m pytest tests/ -v

# Run tests for one phase only
python -m pytest tests/test_lexer.py -v
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_semantic.py -v

# Run the full built-in test suite (both parsers, all 16 cases)
python main.py

# Compile a single expression — top-down parser (default)
python main.py "3 + 5 * 2"

# Compile a single expression — bottom-up parser
python main.py --bottom-up "3 + 5 * 2"

# Compile a .expr source file
python main.py examples/sample.expr

# Run each phase module standalone
python -m compiler.lexer                  # tokenise sample.expr
python -m compiler.parser                 # parse + print AST
python -m compiler.bottom_up_parser       # parse with shift-reduce
python -m compiler.semantic               # analyse + evaluate

# Run a phase on a custom file
python -m compiler.lexer   path/to/file.expr
python -m compiler.parser  path/to/file.expr
```

---

## Project Structure

```
compiler_project/
├── compiler/
│   ├── tokens.py           Token types + Token dataclass
│   ├── lexer.py            Phase 1 — Lexical Analysis
│   ├── ast_nodes.py        AST node dataclasses + tree printer
│   ├── parser.py           Phase 2 — Recursive Descent (top-down)
│   ├── bottom_up_parser.py Phase 2 — Shift-Reduce (bottom-up)
│   ├── semantic.py         Phase 3 — Semantic Analysis
│   └── pipeline.py         Unified 3-phase runner
├── tests/
│   ├── test_lexer.py       21 tests covering RE1, RE2, RE3, errors
│   ├── test_parser.py      27 tests covering both parsers
│   └── test_semantic.py    16 tests covering evaluation and errors
├── examples/
│   └── sample.expr         Example source programs
└── main.py                 Entry point
```

---

## Walkthrough

### The Big Picture

A compiler front end translates raw source text into a validated, structured representation. It does this in three sequential phases — each phase feeds its output into the next.

```
Source text  ──►  LEXER  ──►  Token list  ──►  PARSER  ──►  AST  ──►  SEMANTIC ANALYSER  ──►  Result
  "3+5*2"         Ph.1                          Ph.2               Ph.3
```

If any phase encounters something it cannot handle, it raises a typed error and stops compilation. The error message always tells you which phase caught it and where in the source it occurred (line and column).

---

### Phase 1 — Lexical Analysis (`compiler/lexer.py`)

**What it does:** Breaks the raw source string into a flat list of *tokens* — named chunks of text that the parser can reason about.

**How it works:** Three regular expressions are defined and combined into one master pattern:

```
RE1  =  \d+(?:\.\d+)?             matches numbers:      42  3.14  0.5
RE2  =  [a-zA-Z_][a-zA-Z0-9_]*   matches identifiers:  x  result  _tmp
RE3  =  [+\-*/()=;]               matches operators:    +  -  *  /  (  )  =  ;

MASTER = RE1 | RE2 | COMMENT | RE3 | WHITESPACE | INVALID
```

COMMENT (`//`) must come before RE3 in the master pattern. If it didn't, `//` would be tokenised as two DIVIDE tokens before the comment branch got a chance to match the full two-character sequence. This ordering bug was one of the three we caught and fixed during testing.

The lexer scans left to right. Every character is consumed by exactly one branch:

- **RE1 match** → `NUMBER` token
- **RE2 match** → `IDENTIFIER` token, then reclassified as `PRINT` if the text is in the KEYWORDS dictionary (pattern from the reference implementation)
- **RE3 match** → one of `PLUS MINUS MULTIPLY DIVIDE LPAREN RPAREN ASSIGN SEMICOLON`
- **COMMENT** → silently discarded
- **WHITESPACE** → silently discarded; newlines advance the line counter
- **INVALID** → collected as a `LexerError` — *all* invalid characters in the source are reported, not just the first one

**Example — tokenising `x = 10; y = x + 5`:**

```
LINE:COL   TYPE           VALUE
--------------------------------------
1:1        IDENTIFIER     'x'
1:3        ASSIGN         '='
1:5        NUMBER         '10'
1:7        SEMICOLON      ';'
1:9        IDENTIFIER     'y'
1:11       ASSIGN         '='
1:13       IDENTIFIER     'x'
1:15       PLUS           '+'
1:17       NUMBER         '5'
1:18       EOF            ''
```

**What triggers a Lexer Error:**

```bash
python main.py "3 + @ 2"
# ✗ [Lexer Error] Unexpected character '@' at line 1, column 5
# Compilation halts here — no tokens are passed to the parser.
```

---

### Phase 2 — Syntax Analysis (`compiler/parser.py` and `compiler/bottom_up_parser.py`)

**What it does:** Takes the token list and checks that it follows the grammar. If it does, it builds an Abstract Syntax Tree (AST) that represents the structure of the program.

**We provide two parsers that produce identical ASTs:**

#### Top-Down Recursive Descent Parser (LL(1))

Strategy: starts at the top of the grammar and works downward, calling one method per grammar rule. It reads one token ahead to decide which branch to take — that's what LL(1) means.

The grammar is written so that precedence is encoded directly in the call hierarchy:

```
parse_program()          ← top level
  └─ parse_statement()
       ├─ parse_assignment()    if IDENTIFIER followed by '='
       ├─ parse_print_stmt()    if PRINT
       └─ parse_expr()          ← lowest precedence
              └─ parse_term()   ← medium precedence
                    └─ parse_factor()   ← highest (atoms, parens)
```

`parse_expr` handles `+` and `-`. It calls `parse_term` to get its operands — so by the time `+` is processed, `*` has already been handled deeper in the call stack. That is exactly why `*` binds tighter than `+`.

Left-associativity is implemented by the loop `(op operand)*` rather than recursion. The loop builds the tree left-to-right:

```
10 - 4 - 2  →  BinOp(BinOp(10, '-', 4), '-', 2)   ✓ left-assoc
            ≠  BinOp(10, '-', BinOp(4, '-', 2))    ✗ right-assoc
```

#### Bottom-Up Shift-Reduce Parser (operator-precedence)

Strategy: reads tokens one at a time and pushes them onto a stack (SHIFT). When the top of the stack matches the right-hand side of a grammar rule, it pops those items and pushes the corresponding non-terminal (REDUCE). The tree is built leaves-first, root last.

Precedence is handled by a table. When a binary operator is on the stack and another operator is in the lookahead, the table decides:

```python
PRECEDENCE = {
    PLUS: 1,  MINUS: 1,    # low
    MULTIPLY: 2,  DIVIDE: 2  # high
}
```

**Reduce** if `stack_op precedence >= lookahead precedence` (left-assoc).
**Shift** if `stack_op precedence < lookahead precedence` (lookahead binds tighter).

**Example — parsing `3 + 5 * 2` bottom-up:**

```
Stack                       Lookahead   Action
[]                          3           SHIFT
[3]                         +           REDUCE  3→NUMBER→EXPR
[EXPR(3)]                   +           SHIFT
[EXPR(3), +]                5           SHIFT
[EXPR(3), +, 5]             *           REDUCE  5→NUMBER→EXPR
[EXPR(3), +, EXPR(5)]       *           SHIFT   (* > + so don't reduce yet)
[EXPR(3), +, EXPR(5), *]    2           SHIFT
[EXPR(3), +, EXPR(5), *, 2] EOF         REDUCE  2→EXPR
[EXPR(3), +, EXPR(5), *, EXPR(2)] EOF   REDUCE  EXPR*EXPR → BinOp(5,*,2)
[EXPR(3), +, BinOp(5,*,2)]  EOF         REDUCE  EXPR+EXPR → BinOp(3,+,...)
[BinOp(3,+,BinOp(5,*,2))]  EOF         done
```

Both parsers produce the same AST for `3 + 5 * 2`:

```
Program
└── BinOp  [+]
      ├── Number  3
      └── BinOp  [*]            ← * is deeper = evaluated first
            ├── Number  5
            └── Number  2
Result: 3 + (5*2) = 13, not (3+5)*2 = 16
```

**What triggers a Parser Error:**

```bash
python main.py "3 + * 2"
# Phase 1 passes (all characters are valid tokens)
# Phase 2: ✗ [Parser Error] Unexpected token MULTIPLY ('*') at line 1, column 5

python main.py "(3 + 5"
# ✗ [Parser Error] Expected ')' after expression — found EOF at line 1, column 7
```

---

### Phase 3 — Semantic Analysis (`compiler/semantic.py`)

**What it does:** Walks the AST and enforces rules that the grammar alone cannot catch. It also evaluates every expression to a concrete value.

**Checks performed:**

| Check | Example that triggers it |
|-------|--------------------------|
| Undefined variable | `z + 1` — `z` was never assigned |
| Use before assignment | `y + 1; y = 5` — `y` used on line 1 before being defined |
| Division by zero | `10 / 0` or `10 / (3 - 3)` |
| Type consistency | operands of `+` `-` `*` `/` must be numeric |

**Scoped Symbol Table (from reference implementation):**

The symbol table is a list of dictionaries, one per scope. Variables are looked up from innermost scope outward:

```
scopes = [
    {"x": 10},          ← global scope (index 0)
    {"x": 99, "y": 5},  ← inner scope (index -1, shadows outer x)
]
# _resolve("x") returns 99 (inner), not 10 (outer)
```

When a scope closes, its dictionary is popped — variables declared inside it disappear. This is what variable shadowing means.

**Example — semantic analysis of `x = 10; y = x + 5`:**

```
AST walk:
  1. Assign 'x' = Number(10)
     → evaluate Number(10) → 10
     → store x=10 in symbol table
  2. Assign 'y' = BinOp(Identifier('x'), '+', Number(5))
     → evaluate Identifier('x') → look up 'x' → 10
     → evaluate Number(5)        → 5
     → evaluate BinOp            → 10 + 5 = 15
     → store y=15 in symbol table

Symbol table:   x=10,  y=15
Results:        statement 1 → 10,  statement 2 → 15
```

**What triggers a Semantic Error:**

```bash
python main.py "10 / 0"
# Phase 1 ✓, Phase 2 ✓ (AST is valid), Phase 3:
# ✗ [Semantic Error] Division by zero

python main.py "z + 1"
# ✗ [Semantic Error] Undefined variable 'z'
```

Note that for `10 / 0`, the parser builds the AST successfully — the tree `BinOp(10, '/', 0)` is syntactically legal. Only the semantic phase, which evaluates the expression, catches the error. This shows why all three phases are necessary.

---

### Running the tests

Each test file targets one phase and can be run independently:

```bash
# All 64 tests
python -m pytest tests/ -v

# Lexer tests only (21 tests)
# Covers: RE1 numbers, RE2 identifiers, RE3 operators,
#         keyword reclassification, line/column tracking,
#         comment stripping, whitespace skipping, error collection
python -m pytest tests/test_lexer.py -v

# Parser tests only (27 tests)
# Covers: precedence, left-associativity, AST node types,
#         top-down error cases, bottom-up vs top-down agreement
python -m pytest tests/test_parser.py -v

# Semantic tests only (16 tests)
# Covers: arithmetic evaluation, assignment, symbol table,
#         error cases, scope push/pop, variable shadowing
python -m pytest tests/test_semantic.py -v

# Run a single specific test
python -m pytest tests/test_parser.py::TestPrecedence::test_multiply_binds_tighter_than_add -v

# Run a test group by class name
python -m pytest tests/test_parser.py::TestBottomUpMatchesTopDown -v
python -m pytest tests/test_semantic.py::TestScopeManagement -v
```

---

### Testing your own inputs

```bash
# Any valid arithmetic expression
python main.py "2 * 3 + 4 * 5"          # → 26
python main.py "10 - 4 - 2"             # → 4 (not 8 — left-assoc)
python main.py "(2 + 3) * (4 - 1)"      # → 15
python main.py "1.5 * 4"                # → 6.0

# Variables and assignment
python main.py "a = 5; b = a * 2; b"    # → 10
python main.py "x = 10; y = x + 5"      # symbol table: x=10, y=15

# print() statement
python main.py "print(3 + 4)"           # prints 7 during semantic phase

# Comments are stripped before tokenising
python main.py "3 + 5 // add five"      # → 8

# Compare both parsers on the same input
python main.py          "3 + 5 * 2"    # top-down
python main.py --bottom-up "3 + 5 * 2" # bottom-up (same AST, different strategy)

# Error cases — try these to see each phase's error handling
python main.py "3 + @ 2"               # Lexer Error: '@' not in RE1|RE2|RE3
python main.py "3 + * 2"               # Parser Error: two operators in a row
python main.py "(3 + 5"                # Parser Error: unclosed parenthesis
python main.py "print 42"              # Parser Error: missing '(' after print
python main.py "z + 1"                 # Semantic Error: undefined variable
python main.py "y + 1; y = 5"          # Semantic Error: use before assignment
python main.py "10 / 0"               # Semantic Error: division by zero
python main.py "10 / (3 - 3)"         # Semantic Error: div by zero (expression)
```

---

### Key Design Decisions

| Decision | Why |
|----------|-----|
| RE1\|RE2\|RE3 master pattern | Single-pass tokenisation; each branch is isolated and testable |
| COMMENT before RE3 in master | `//` must match as one comment token before `/` matches as DIVIDE twice |
| Recursive descent for top-down | One method per grammar rule — reading the code IS reading the grammar |
| Precedence encoded in call depth | `parse_expr` calls `parse_term` which calls `parse_factor` — deeper = tighter binding |
| Loop `(op operand)*` for left-assoc | Builds BinOp left-to-right without right-recursive grammar rules |
| PRECEDENCE table for bottom-up | Explicit numeric comparison decides shift vs. reduce at every binary operator |
| `frozen=True, slots=True` on dataclasses | Tokens and AST nodes are immutable and memory-efficient (from reference impl.) |
| Scoped symbol table (list of dicts) | Supports variable shadowing; inner scope is index -1, outer is index 0 |
| Errors collected not thrown (lexer) | All invalid characters reported in one pass, not just the first |
| (tokens, errors) return from Lexer | Caller decides whether to halt or continue after lex errors |
