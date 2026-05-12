# Front-End Compiler — Project Instructions & Specification

## Project Title
**Python Front-End Compiler for Arithmetic Expressions**

---

## 1. Project Overview

This project implements the **front end of a compiler** in Python. The front end is the part of a compiler responsible for understanding the source code — it does NOT generate machine code or bytecode. Instead, it analyses the source text in three sequential phases and produces a structured, validated representation of the program.

The three phases are:

| Phase | Name | Input | Output |
|-------|------|-------|--------|
| 1 | Lexical Analysis | Raw source string | Stream of tokens |
| 2 | Syntax Analysis | Token stream | Abstract Syntax Tree (AST) |
| 3 | Semantic Analysis | AST | Evaluated results + symbol table |

The compiler targets **arithmetic expressions with variable assignment**, for example:

```
x = 10
y = x + 5 * 2
(3 + 4) * y
```

---

## 2. Regular Expressions

The lexer is built from exactly **three base regular expressions** that are combined into one master token pattern.

### RE1 — Numbers
Matches integer and floating-point numeric literals.

```
RE1 = \d+(\.\d+)?
```

| Example match | Type |
|---------------|------|
| `42` | Integer |
| `3.14` | Float |
| `0.5` | Float |

### RE2 — Identifiers
Matches variable names. Must start with a letter or underscore, followed by any mix of letters, digits, or underscores.

```
RE2 = [a-zA-Z_][a-zA-Z0-9_]*
```

| Example match | Notes |
|---------------|-------|
| `x` | Single-letter variable |
| `result` | Multi-char variable |
| `_temp` | Underscore-prefixed |
| `var1` | With digit suffix |

### RE3 — Operators & Symbols
Matches all arithmetic operators and structural punctuation.

```
RE3 = [+\-*/()=;]
```

| Character | Meaning |
|-----------|---------|
| `+` | Addition |
| `-` | Subtraction |
| `*` | Multiplication |
| `/` | Division |
| `(` | Left parenthesis |
| `)` | Right parenthesis |
| `=` | Assignment |
| `;` | Statement terminator (optional) |

### Combined Token Pattern
The three REs are joined using alternation (`|`). Order matters — more specific patterns must appear before general ones:

```
MASTER_PATTERN = RE1 | RE2 | RE3 | WHITESPACE | INVALID
```

Where `WHITESPACE` silently skips spaces/tabs/newlines, and `INVALID` catches any character that matches none of the above, triggering a Lexer Error.

---

## 3. Token Types

After the lexer matches text using the combined pattern, each match is classified into one of these token types:

| Token Type | Example | Source RE |
|------------|---------|-----------|
| `NUMBER` | `42`, `3.14` | RE1 |
| `IDENTIFIER` | `x`, `result` | RE2 |
| `PLUS` | `+` | RE3 |
| `MINUS` | `-` | RE3 |
| `MULTIPLY` | `*` | RE3 |
| `DIVIDE` | `/` | RE3 |
| `LPAREN` | `(` | RE3 |
| `RPAREN` | `)` | RE3 |
| `ASSIGN` | `=` | RE3 |
| `SEMICOLON` | `;` | RE3 |
| `EOF` | *(end of input)* | synthetic |

---

## 4. Grammar — Precedence & Associativity

The parser is driven by a **context-free grammar (CFG)** written to encode operator precedence directly into its structure. Lower-precedence operators appear at the top of the grammar; higher-precedence operators appear deeper.

```
program    →  statement* EOF

statement  →  assignment
           |  expr ( ';' )?

assignment →  IDENTIFIER '=' expr ( ';' )?

expr       →  term ( ('+' | '-') term )*        ← lowest precedence

term       →  factor ( ('*' | '/') factor )*    ← medium precedence

factor     →  NUMBER
           |  IDENTIFIER
           |  '(' expr ')'                      ← highest precedence (grouping)
```

### Precedence Table (low → high)

| Level | Operators | Rule in Grammar |
|-------|-----------|-----------------|
| 1 (lowest) | `+`, `-` | `expr` |
| 2 | `*`, `/` | `term` |
| 3 (highest) | `(` `)` | `factor` |

### Associativity
All binary operators (`+`, `-`, `*`, `/`) are **left-associative**.

This is achieved by the repetition loop `(op operand)*` in each grammar rule, which builds the AST left-to-right:

```
3 - 2 - 1  →  BinOp(BinOp(3, '-', 2), '-', 1)   ✓ left-assoc
           ≠  BinOp(3, '-', BinOp(2, '-', 1))   ✗ right-assoc
```

---

## 5. Parser Type — Recursive Descent (LL(1))

The parser used is a **Recursive Descent Parser**, which is a top-down, predictive parser.

| Property | Value |
|----------|-------|
| Strategy | Top-down |
| Look-ahead | 1 token (LL(1)) |
| Implementation | One Python function per grammar rule |
| AST construction | Yes — nodes built during parsing |
| Error recovery | No — halts at first syntax error |

**Why Recursive Descent?**
- Directly mirrors the grammar rules — easy to read and teach
- Each grammar rule becomes one function (`parse_expr`, `parse_term`, `parse_factor`)
- Naturally handles precedence through the call hierarchy
- No parsing table required

**Call Hierarchy** (reflects precedence):
```
parse_program()
  └── parse_statement()
        ├── parse_assignment()   (if IDENTIFIER followed by '=')
        └── parse_expr()         (lowest precedence — called first)
              └── parse_term()   (medium precedence)
                    └── parse_factor()  (highest — NUMBER, ID, parens)
```

---

## 6. Abstract Syntax Tree (AST)

The parser constructs an AST — a tree where each node represents a language construct. Leaf nodes are literals or identifiers; internal nodes are operations.

### Node Types

| Node | Fields | Represents |
|------|--------|------------|
| `ProgramNode` | `statements: list` | The whole program |
| `AssignNode` | `name: str, value: ASTNode` | Variable assignment |
| `BinOpNode` | `left, op, right` | Binary arithmetic operation |
| `NumberNode` | `value: int/float` | Numeric literal |
| `IdentifierNode` | `name: str` | Variable reference |

### Example AST

Input: `x = 3 + 5 * 2`

```
Program
└── Assign: 'x'
      └── BinOp: '+'
            ├── Number: 3
            └── BinOp: '*'
                  ├── Number: 5
                  └── Number: 2
```

The `*` sits lower in the tree (evaluated first), correctly encoding that multiplication has higher precedence than addition.

---

## 7. Error Handling

Errors are caught per phase. Each error includes a descriptive message and the position in the source string where it occurred.

### Phase 1 — Lexer Errors
Triggered when the source contains a character that matches none of RE1, RE2, or RE3.

| Error | Trigger | Example input |
|-------|---------|---------------|
| Invalid character | Unknown symbol in source | `3 + @ 2` |

### Phase 2 — Parser Errors
Triggered when the token stream does not conform to the grammar.

| Error | Trigger | Example input |
|-------|---------|---------------|
| Unexpected token | Token appears where it is not expected | `3 + * 2` |
| Missing token | Expected token is absent | `(3 + 5` (no closing paren) |

### Phase 3 — Semantic Errors
Triggered after a valid AST is produced, during evaluation.

| Error | Trigger | Example input |
|-------|---------|---------------|
| Undefined variable | Variable used before assignment | `z + 1` (z never set) |
| Division by zero | Divisor evaluates to 0 | `10 / 0` |
| Type mismatch | Non-numeric operand (future extension) | N/A in base version |

---

## 8. Test Cases

The following inputs will be used to demonstrate the compiler. Each tests a specific aspect.

| # | Input | Expected Outcome | Tests |
|---|-------|-----------------|-------|
| 1 | `3 + 5 * 2` | Result: 13 (not 16) | Precedence (* before +) |
| 2 | `(2 + 3) * 4` | Result: 20 | Parentheses override precedence |
| 3 | `10 - 4 - 2` | Result: 4 (not 8) | Left-associativity |
| 4 | `x = 10; y = x + 5` | x=10, y=15 | Assignment + variable reuse |
| 5 | `10 / 0` | Semantic Error: division by zero | Semantic error handling |
| 6 | `z + 1` | Semantic Error: undefined variable | Semantic error handling |
| 7 | `3 + @ 2` | Lexer Error: invalid character '@' | Lexer error handling |
| 8 | `3 + * 2` | Parser Error: unexpected token '*' | Syntax error handling |
| 9 | `(3 + 5` | Parser Error: expected ')' | Missing token error |

---

## 9. Implementation Plan

The compiler will be implemented as a single Python file `compiler.py` structured in clearly labelled sections:

```
Section 0 — Regular Expressions (RE1, RE2, RE3 defined and combined)
Section 1 — Token types and Token dataclass
Section 2 — Lexer class (Phase 1)
Section 3 — AST node dataclasses
Section 4 — Parser class (Phase 2) — Recursive Descent
Section 5 — AST printer (tree visualisation)
Section 6 — Semantic Analyser class (Phase 3)
Section 7 — compile_source() pipeline function (runs all 3 phases)
Section 8 — Entry point with all test cases
```

Each section prints a clearly labelled header when run, so the output explicitly shows which compiler phase is active and what it produced.

---

## 10. Running the Compiler

```bash
python compiler.py
```

To test a single custom expression, the `compile_source()` function can be called directly:

```python
from compiler import compile_source
compile_source("a = 4 * (2 + 3)")
```

---

## 11. Language at a Glance

```
# Valid programs the compiler accepts:

42                      # bare number
3 + 5 * 2               # arithmetic with precedence
(2 + 3) * 4             # parenthesised grouping
x = 10                  # assignment
y = x + 5               # variable use in expression
x = 10; y = x * 2       # multiple statements with semicolons
10 - 4 - 2              # left-associative subtraction

# Invalid programs and which phase catches them:

3 + @ 2       → Lexer Error    (@ is not in RE1, RE2, or RE3)
3 + * 2       → Parser Error   (two operators in a row)
(3 + 5        → Parser Error   (unclosed parenthesis)
z + 1         → Semantic Error (z undefined)
10 / 0        → Semantic Error (division by zero)
```
