# Detailed Code Flow Walkthrough with Examples

## Complete Example: `"(2 + 3) * 4"`

### PHASE 1: LEXICAL ANALYSIS

**Input String:**
```
"(2 + 3) * 4"
```

**Lexer Processing:**

```python
source = "(2 + 3) * 4"

# The _MASTER regex scans left-to-right, finding matches

Match 1: Position 0, String: "("
    kind = "OPERATOR"
    value = "("
    line = 1, col = 1
    → Token(LPAREN, "(", 1, 1)

Match 2: Position 1, String: "2"
    kind = "NUMBER"
    value = "2"
    line = 1, col = 2
    → Token(NUMBER, "2", 1, 2)

Match 3: Position 3, String: " "
    kind = "WHITESPACE"
    value = " "
    → SKIP (just track for line numbers)

Match 4: Position 4, String: "+"
    kind = "OPERATOR"
    value = "+"
    line = 1, col = 5
    → Token(PLUS, "+", 1, 5)

Match 5: Position 6, String: " "
    kind = "WHITESPACE"
    → SKIP

Match 6: Position 7, String: "3"
    kind = "NUMBER"
    value = "3"
    line = 1, col = 8
    → Token(NUMBER, "3", 1, 8)

Match 7: Position 8, String: ")"
    kind = "OPERATOR"
    value = ")"
    line = 1, col = 9
    → Token(RPAREN, ")", 1, 9)

Match 8: Position 10, String: " "
    kind = "WHITESPACE"
    → SKIP

Match 9: Position 11, String: "*"
    kind = "OPERATOR"
    value = "*"
    line = 1, col = 12
    → Token(MULTIPLY, "*", 1, 12)

Match 10: Position 13, String: " "
    kind = "WHITESPACE"
    → SKIP

Match 11: Position 14, String: "4"
    kind = "NUMBER"
    value = "4"
    line = 1, col = 15
    → Token(NUMBER, "4", 1, 15)

(End of string)
→ Token(EOF, "", 1, 16)
```

**Lexer Output:**
```python
tokens = [
    Token(LPAREN, "(", 1, 1),
    Token(NUMBER, "2", 1, 2),
    Token(PLUS, "+", 1, 5),
    Token(NUMBER, "3", 1, 8),
    Token(RPAREN, ")", 1, 9),
    Token(MULTIPLY, "*", 1, 12),
    Token(NUMBER, "4", 1, 15),
    Token(EOF, "", 1, 16)
]

errors = []  # No lexical errors
```

**Console Output:**
```
──────────────────────────────────────────────────────────────
  PHASE 1 · LEXICAL ANALYSIS
──────────────────────────────────────────────────────────────
  RE1 (numbers)     : \d+(?:\.\d+)?
  RE2 (identifiers) : [a-zA-Z_][a-zA-Z0-9_]*
  RE3 (operators)   : [+\-*/()=;]
  Master pattern    : RE1 | RE2 | COMMENT | RE3 | ...

  LINE:COL  TYPE        VALUE
  ─────────────────────────────
  1:1       LPAREN      '('
  1:2       NUMBER      '2'
  1:5       PLUS        '+'
  1:8       NUMBER      '3'
  1:9       RPAREN      ')'
  1:12      MULTIPLY    '*'
  1:15      NUMBER      '4'
  1:16      EOF         ''

  ✓ 7 token(s) produced.
```

---

### PHASE 2: SYNTAX ANALYSIS (Recursive Descent Parser)

**Input:** Token list from Phase 1

**Parser State:**
```python
parser = Parser(tokens)
parser.pos = 0  # Start at position 0 (LPAREN)
```

**Parsing Sequence (Call Stack Trace):**

```python
# Call: parser.parse() → program()

program()                                [pos=0: LPAREN]
│
└─ statement()                           [pos=0: LPAREN]
   │
   └─ expr()                            [pos=0: LPAREN]
      │
      ├─ term()                         [pos=0: LPAREN]
      │  │
      │  ├─ factor()                    [pos=0: LPAREN]
      │  │  │
      │  │  ├─ Check: TokenType.LPAREN  ✓ Match!
      │  │  │  _advance()               [pos=1: NUMBER]
      │  │  │
      │  │  ├─ Recursively parse inner expression
      │  │  │  expr()                   [pos=1: NUMBER]
      │  │  │  │
      │  │  │  ├─ term()                [pos=1: NUMBER]
      │  │  │  │  │
      │  │  │  │  ├─ factor()           [pos=1: NUMBER]
      │  │  │  │  │  │
      │  │  │  │  │  ├─ Check: NUMBER   ✓ Match!
      │  │  │  │  │  │  value = 2.0
      │  │  │  │  │  │  _advance()      [pos=2: PLUS]
      │  │  │  │  │  │  return Number(2.0)
      │  │  │  │  │  
      │  │  │  │  │  [pos=2: PLUS not in ('*', '/')]
      │  │  │  │  │  return Number(2.0)
      │  │  │  │  
      │  │  │  │  [pos=2: PLUS matches ('+' | '-')]
      │  │  │  │  op_value = '+'
      │  │  │  │  _advance()            [pos=3: NUMBER]
      │  │  │  │
      │  │  │  │  ├─ factor()           [pos=3: NUMBER]
      │  │  │  │  │  │
      │  │  │  │  │  ├─ Check: NUMBER   ✓ Match!
      │  │  │  │  │  │  value = 3.0
      │  │  │  │  │  │  _advance()      [pos=4: RPAREN]
      │  │  │  │  │  │  return Number(3.0)
      │  │  │  │  │  
      │  │  │  │  ├─ left = BinOp(Number(2.0), '+', Number(3.0))
      │  │  │  │  │
      │  │  │  │  [pos=4: RPAREN not in ('+', '-')]
      │  │  │  │  return BinOp(Number(2.0), '+', Number(3.0))
      │  │  │  
      │  │  │  [pos=4: no more operators]
      │  │  │  return BinOp(Number(2.0), '+', Number(3.0))
      │  │  │
      │  │  ├─ _consume(TokenType.RPAREN, "Expected ')'")
      │  │  │  [pos=4: RPAREN] ✓ Match!
      │  │  │  _advance()               [pos=5: MULTIPLY]
      │  │  │  return Token(RPAREN, ')', 1, 9)
      │  │  │
      │  │  └─ return expr result: BinOp(Number(2.0), '+', Number(3.0))
      │  │
      │  └─ return BinOp(Number(2.0), '+', Number(3.0))  ← from factor()
      │  
      │  [pos=5: MULTIPLY matches ('*' | '/')]
      │  op_value = '*'
      │  _advance()                     [pos=6: NUMBER]
      │
      │  ├─ factor()                    [pos=6: NUMBER]
      │  │  │
      │  │  ├─ Check: NUMBER            ✓ Match!
      │  │  │  value = 4.0
      │  │  │  _advance()               [pos=7: EOF]
      │  │  │  return Number(4.0)
      │  │
      │  ├─ left = BinOp(
      │  │           BinOp(Number(2.0), '+', Number(3.0)),
      │  │           '*',
      │  │           Number(4.0)
      │  │       )
      │  │
      │  [pos=7: EOF not in ('*', '/')]
      │  return left
      │
      [pos=7: EOF not in ('+', '-')]
      return left

└─ _consume(TokenType.EOF, "Expected EOF")
   [pos=7: EOF] ✓ Match!
   return Token(EOF, '', 1, 16)

Return from program():
    Program(
        statements=(
            BinOp(
                BinOp(Number(2.0), '+', Number(3.0)),
                '*',
                Number(4.0)
            ),
        )
    )
```

**Final AST:**
```
Program
└── BinOp  [*]
      ├── BinOp  [+]
      │     ├── Number  2
      │     └── Number  3
      └── Number  4
```

**Interpretation:**
```
(2 + 3) * 4
   │      │
   │      └─ Evaluated when factor() is called with pos=6
   │
   └─ Evaluated when expr() is called recursively inside parentheses
```

**Console Output:**
```
──────────────────────────────────────────────────────────────
  PHASE 2 · SYNTAX ANALYSIS
──────────────────────────────────────────────────────────────
  Parser        : Recursive Descent  (top-down, LL(1))
  Associativity : Left-to-right for all binary operators
  Precedence    : +/-  <  */  <  ()  <  atoms  (low → high)

  Abstract Syntax Tree:

    Program
    └── BinOp  [*]
          ├── BinOp  [+]
          │     ├── Number  2
          │     └── Number  3
          └── Number  4

  ✓ AST built successfully.
```

---

### PHASE 3: SEMANTIC ANALYSIS

**Input:** AST from Phase 2

**Initial State:**
```python
analyzer = SemanticAnalyzer()
analyzer.scopes = [{}]  # One global scope, empty
```

**Evaluation Walkthrough:**

```python
# Call: analyzer.analyze(Program(...))

analyze(Program(statements=(BinOp(...),)))
│
├─ Process each statement in Program.statements
│
├─ Statement 1: BinOp(BinOp(Number(2), '+', Number(3)), '*', Number(4))
│  │
│  ├─ analyze(BinOp(BinOp(...), '*', Number(4)))
│  │  │
│  │  ├─ left = analyze(BinOp(Number(2), '+', Number(3)))
│  │  │  │
│  │  │  ├─ left = analyze(Number(2))
│  │  │  │  └─ return 2.0
│  │  │  │
│  │  │  ├─ right = analyze(Number(3))
│  │  │  │  └─ return 3.0
│  │  │  │
│  │  │  ├─ op = '+'
│  │  │  ├─ Compute: 2.0 + 3.0 = 5.0
│  │  │  └─ return 5.0
│  │  │
│  │  ├─ right = analyze(Number(4))
│  │  │  └─ return 4.0
│  │  │
│  │  ├─ op = '*'
│  │  ├─ Compute: 5.0 * 4.0 = 20.0
│  │  └─ return 20.0
│  │
│  └─ results.append(20.0)

Return: [20.0]
```

**Final State:**
```python
analyzer.scopes = [{}]  # No variables assigned
analyzer.symbol_table = {}

eval_results = [20.0]
```

**Console Output:**
```
──────────────────────────────────────────────────────────────
  PHASE 3 · SEMANTIC ANALYSIS
──────────────────────────────────────────────────────────────
  Checks : undefined variables  |  division by zero  |  type consistency
  Scopes : push on block entry, pop on block exit  (variable shadowing)

  (No variables assigned, so symbol table is empty)

  Evaluation results:
    statement 1  →  20.0

  ✓ Semantic analysis passed.
================================================================
```

---

## Comparison: Two Different Parsers

### Same Input: `"3 * 2 + 1"`

Both parsers produce the same AST (correct parsing of precedence):
```
BinOp [+]
├── BinOp [*]
│   ├── Number 3
│   └── Number 2
└── Number 1
```

But they get there differently!

### Top-Down Parser (LL(1)) - How It Works

```
Approach: "Predictive" - look ahead 1 token, decide what to do

expr() reads: 3 * 2 + 1
  → Calls term() first (lower precedence before higher)
  → term() reads: 3 * 2
    → Calls factor()  → Number(3)
    → Sees '*', calls factor() again
    → Sees '2', creates BinOp(3, '*', 2)
    → Sees '+' (not '*' or '/'), returns BinOp(3, '*', 2)
  → expr() now has: BinOp(3, '*', 2)
  → Sees '+', calls term()
  → term() reads: 1
    → Calls factor() → Number(1)
    → Returns Number(1)
  → Creates: BinOp(BinOp(3, '*', 2), '+', Number(1))

Position: Top → Down (start at high level, recurse to atoms)
```

### Bottom-Up Parser (Shift-Reduce) - How It Works

```
Approach: "Reduce when possible" - use operator precedence table

Input stack: 3 * 2 + 1

1. Shift 3              stack: [3]
2. Shift *              stack: [3, *]
3. Shift 2              stack: [3, *, 2]
4. Reduce by 2 * 3      stack: [BinOp(3, '*', 2)]
   (because * has higher precedence than +, reduce immediately)
5. Shift +              stack: [BinOp(...), +]
6. Shift 1              stack: [BinOp(...), +, 1]
7. Reduce by 1 + ...    stack: [BinOp(BinOp(...), '+', 1)]
8. Done

Position: Bottom → Up (start at atoms, reduce to high level)
```

---

## Error Examples

### Error Case 1: Lexical Error

**Input:** `"3 + @ 5"`

**Lexer Processing:**
```
Match 1: "3"    → Token(NUMBER, "3")
Match 2: " "    → SKIP
Match 3: "+"    → Token(PLUS, "+")
Match 4: " "    → SKIP
Match 5: "@"    → kind = "INVALID"
                → LexerError("Unexpected character '@' at line 1, column 5")
                → Add to errors list (don't stop!)
Match 6: " "    → SKIP
Match 7: "5"    → Token(NUMBER, "5")
```

**Output:**
```
tokens = [Token(NUMBER, "3"), Token(PLUS, "+"), Token(NUMBER, "5"), Token(EOF, "")]
errors = [LexerError("Unexpected character '@' at line 1, column 5")]

Console Output:
  ✗ [Lexer Error] Unexpected character '@' at line 1, column 5

  Lexical errors found — compilation halted.
================================================================
```

Compilation stops here! Parser and semantic analyzer are not run.

### Error Case 2: Parse Error

**Input:** `"3 + * 2"` (consecutive operators)

**Tokens:**
```
[NUMBER(3), PLUS, MULTIPLY, NUMBER(2), EOF]
```

**Parser Processing:**
```
expr()
├─ term()
│  ├─ factor()
│  │  └─ Number(3)
│  └─ Sees PLUS (not '*' or '/'), returns Number(3)
├─ Sees PLUS, calls term() again  [pos=2: MULTIPLY]
│  ├─ factor()
│  │  │
│  │  ├─ Check: MULTIPLY
│  │  │  But factor() expects: NUMBER, IDENTIFIER, or LPAREN
│  │  │  MULTIPLY is none of these!
│  │  │
│  │  └─ raise ParseError(
│  │         "Expected NUMBER/IDENTIFIER/LPAREN, "
│  │         "found MULTIPLY '*' at line 1, column 5"
│  │     )
```

**Output:**
```
  ✗ [Parser Error] Expected NUMBER, IDENTIFIER, or '(', 
                   found MULTIPLY ('*') at line 1, column 5

  Syntax error found — compilation halted.
================================================================
```

Parser halts! Semantic analyzer is not run.

### Error Case 3: Semantic Error

**Input:** `"10 / 0"` (division by zero)

**Tokens:** [NUMBER(10), DIVIDE, NUMBER(0), EOF]
**AST:** BinOp(Number(10), '/', Number(0))

**Semantic Analyzer Processing:**
```
analyze(BinOp(Number(10), '/', Number(0)))
├─ left = analyze(Number(10))
│  └─ return 10.0
├─ right = analyze(Number(0))
│  └─ return 0.0
├─ op = '/'
├─ Check: if right == 0
│  └─ YES! Raise SemanticError("Division by zero")
```

**Output:**
```
  ✗ [Semantic Error] Division by zero

  Semantic error found — compilation halted.
================================================================
```

---

## Code Patterns Used

### Pattern 1: Recursive Descent

```python
# Parser methods mirror grammar rules

def expr(self):
    """expr → term (('+' | '-') term)*"""
    left = self.term()
    while self._match(PLUS, MINUS):
        op = ...
        right = self.term()
        left = BinOp(left, op, right)
    return left
```

**Key Idea:** Each method handles one grammar rule. Recursion naturally encodes precedence.

### Pattern 2: AST Visitor (Semantic Analyzer)

```python
def analyze(self, node):
    """Process different node types"""
    if isinstance(node, BinOp):
        return self.eval_binop(node)
    elif isinstance(node, Number):
        return node.value
    elif isinstance(node, Identifier):
        return self._resolve(node.name)
    # ... etc
```

**Key Idea:** Single method dispatches based on node type. Recursive calls build the solution.

### Pattern 3: Error Collection (not early exit)

```python
def tokenize(self):
    errors = []
    for match in _MASTER.finditer(source):
        if invalid:
            errors.append(error)  # Don't stop, collect all
        else:
            tokens.append(token)
    return tokens, errors
```

**Key Idea:** Continue processing to report ALL errors, not just the first.

---

## Summary: Data Transformations

```
Input String
    ↓
┌─────────────────┐
│ Lexer            │  Transforms: string → tokens
│                  │  Using: regex patterns (HARDCODED)
│ lexer.py         │  
└────────┬─────────┘
         ↓
Token Stream
    ↓
┌─────────────────┐
│ Parser           │  Transforms: tokens → AST
│                  │  Using: grammar rules (HARDCODED)
│ parser.py OR     │  
│ bottom_up_parser │  
└────────┬─────────┘
         ↓
Abstract Syntax Tree
    ↓
┌─────────────────┐
│ Semantic         │  Transforms: AST → results
│ Analyzer         │  Using: semantic rules (HARDCODED)
│                  │
│ semantic.py      │  Produces: symbol table, eval results
└────────┬─────────┘
         ↓
Symbol Table + Evaluation Results
    ↓
┌─────────────────┐
│ Report           │  Transforms: data → HTML
│ Generator        │
│ report.py        │
└─────────────────┘
    ↓
HTML Report (browser)
```

Each stage is **deterministic and rule-based** - given the same input, always produces the same output.
