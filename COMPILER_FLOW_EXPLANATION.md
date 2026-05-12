# Complete Compiler Flow Explanation

## Overview: Input to Output Journey

```
┌─────────────┐
│ USER INPUT  │  "x = 10; y = x + 5"
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│ PHASE 1: LEXICAL ANALYSIS (Lexer)    │ ◄── compiler/lexer.py
│  Input: Raw string                   │
│  Output: Token stream                │
└──────┬──────────────────────────────┘
       │
       ▼ Tokens: [IDENT(x), ASSIGN, NUMBER(10), SEMICOLON, ...]
       │
       ▼
┌──────────────────────────────────────┐
│ PHASE 2: SYNTAX ANALYSIS (Parser)    │ ◄── compiler/parser.py
│  Input: Token stream                 │     or compiler/bottom_up_parser.py
│  Output: Abstract Syntax Tree (AST)  │
└──────┬──────────────────────────────┘
       │
       ▼ AST: Program
        │   ├── Assign (x = 10)
        │   └── Assign (y = x + 5)
       │
       ▼
┌──────────────────────────────────────┐
│ PHASE 3: SEMANTIC ANALYSIS           │ ◄── compiler/semantic.py
│  Input: AST                          │
│  Output: Evaluated results +         │
│           Symbol table               │
└──────┬──────────────────────────────┘
       │
       ▼ Results: Symbol table = {x: 10, y: 15}
       │          Evaluation results = [10, 15]
       │
       ▼
┌──────────────────────────────────────┐
│ OUTPUT GENERATION                    │ ◄── compiler/report.py
│  Creates: compiler_report.html       │     compiler/visualizer.py
└──────────────────────────────────────┘
```

---

## PHASE 1: LEXICAL ANALYSIS (Tokenization)

**File:** `compiler/lexer.py`  
**Task:** Break raw text into meaningful tokens

### How It Works

The lexer uses **three base regular expressions** that are combined into ONE master pattern:

```python
# HARDCODED PATTERNS (fixed by grammar design):
RE1_NUMBER     = r"(?P<NUMBER>\d+(?:\.\d+)?)"           # Numbers: 42, 3.14
RE2_IDENTIFIER = r"(?P<IDENTIFIER>[a-zA-Z_][a-zA-Z0-9_]*)"  # Variables: x, y, name
RE3_OPERATOR   = r"(?P<OPERATOR>[+\-*/()=;])"           # Operators: +, -, *, /, (, ), =, ;
```

**Master Pattern (HARDCODED):**
```
RE1 | RE2 | COMMENT | RE3 | WHITESPACE | INVALID
```

The order matters! Comments must come BEFORE RE3 so `//` is recognized as a comment, not two `/` tokens.

### Step-by-Step Example

**Input:** `"x = 10 // comment"`

```
Match 1: "x"           → kind=IDENTIFIER → Token(IDENTIFIER, "x", line=1, col=1)
Match 2: " "           → kind=WHITESPACE → SKIP (only track newlines)
Match 3: "="           → kind=OPERATOR   → Token(ASSIGN, "=", line=1, col=3)
Match 4: " "           → kind=WHITESPACE → SKIP
Match 5: "10"          → kind=NUMBER     → Token(NUMBER, "10", line=1, col=5)
Match 6: " // comment" → kind=COMMENT    → SKIP (entire comment stripped)
Match 7: EOF           → (implicit)      → Token(EOF, "", line=1, col=...)
```

**Output:** Token list
```python
[
    Token(IDENTIFIER, "x", line=1, col=1),
    Token(ASSIGN, "=", line=1, col=3),
    Token(NUMBER, "10", line=1, col=5),
    Token(EOF, "", line=1, col=12)
]
```

### Code Structure

```python
class Lexer:
    def __init__(self, source: str):
        self.source = source
    
    def tokenize(self) -> tuple[list[Token], list[LexerError]]:
        tokens = []
        errors = []
        line = 1
        line_start = 0
        
        for match in _MASTER.finditer(self.source):
            kind = match.lastgroup  # "NUMBER", "IDENTIFIER", "OPERATOR", etc.
            value = match.group()    # The matched string
            col = match.start() - line_start + 1  # Column number
            
            if kind == "COMMENT":
                continue  # SKIP comments
            elif kind == "WHITESPACE":
                # Track newlines for line numbers
                newlines = value.count("\n")
                if newlines:
                    line += newlines
                    line_start = ...
                continue
            elif kind == "INVALID":
                # Collect error, don't stop (report all errors)
                errors.append(LexerError(...))
            else:
                # Create token for NUMBER, IDENTIFIER, OPERATOR
                tokens.append(Token(kind, value, line, col))
        
        tokens.append(Token(EOF, "", line, col))  # Add EOF marker
        return tokens, errors
```

### Hardcoded vs Dynamic

| Aspect | Type | Details |
|--------|------|---------|
| **Regex patterns (RE1, RE2, RE3)** | HARDCODED | Fixed by language grammar design |
| **Master pattern order** | HARDCODED | Comments before operators so `//` works |
| **Token mapping** | HARDCODED | `_OPERATOR_MAP = {"+": PLUS, "-": MINUS, ...}` |
| **Comment syntax** | HARDCODED | `//` means rest-of-line is comment |
| **Whitespace handling** | HARDCODED | Spaces/tabs skipped, newlines tracked |
| **Input characters** | DYNAMIC | What user types |
| **Token output** | DYNAMIC | Generated from input |

---

## PHASE 2: SYNTAX ANALYSIS (Parsing)

**Files:** `compiler/parser.py` (top-down, LL(1))  
**Or:** `compiler/bottom_up_parser.py` (bottom-up, shift-reduce)

**Task:** Build an Abstract Syntax Tree (AST) from tokens, checking grammar rules

### The Grammar (HARDCODED)

```
program    → statement* EOF
statement  → assignment | print_stmt | expr ';'?
assignment → IDENTIFIER '=' expr ';'?
print_stmt → 'print' '(' expr ')' ';'?
expr       → term (('+' | '-') term)*          ← lowest precedence (handled first in recursion)
term       → factor (('*' | '/') factor)*      ← medium precedence
factor     → NUMBER | IDENTIFIER | '(' expr ')' ← highest precedence (atoms)
```

**Key Design:** Precedence is encoded in the **call hierarchy**. Lower-precedence rules call higher-precedence rules, so:
- `expr()` calls `term()` (so `+` binds looser than `*`)
- `term()` calls `factor()` (so `*` binds looser than parentheses)
- `factor()` recognizes atoms (numbers, variables, parenthesized expressions)

### Top-Down Parser Example (LL(1))

**Input:** `"3 + 5 * 2"`  
**Tokens:** `[NUMBER(3), PLUS, NUMBER(5), MULTIPLY, NUMBER(2), EOF]`

```
parse()
├─ program()
│  └─ statement() [position 0: NUMBER(3)]
│     └─ expr()                           ← Start: try to parse an expression
│        └─ term()
│           └─ factor()
│              └─ Token(NUMBER, 3)      ← Match NUMBER → Number(3)
│                 [position 1: PLUS]
│        [position 1: PLUS matches ('+' | '-')]
│        └─ '+' found, continue loop
│        └─ term()
│           └─ factor()
│              └─ Token(NUMBER, 5)      ← Number(5)
│                 [position 3: MULTIPLY]
│           [position 3: MULTIPLY matches ('*' | '/')]
│           └─ '*' found, continue loop
│           └─ factor()
│              └─ Token(NUMBER, 2)      ← Number(2)
│                 [position 5: EOF]
│           [position 5: no ('*' | '/')]
│           └─ return BinOp(Number(5), '*', Number(2))
│        [position 5: no ('+' | '-')]
│        └─ return BinOp(Number(3), '+', BinOp(...))
│
└─ Return: Program([BinOp(Number(3), '+', BinOp(Number(5), '*', Number(2)))])
```

**Output AST:**
```
Program
└── BinOp  [+]
      ├── Number  3
      └── BinOp  [*]
            ├── Number  5
            └── Number  2
```

**Result:** `3 + (5 * 2)` because `*` binds tighter (multiplication evaluated first)

### Parser Code Structure

```python
class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0  # Current position in token stream
    
    def _current(self) -> Token:
        """Return token at current position"""
        return self.tokens[self.pos]
    
    def _advance(self) -> Token:
        """Move to next token"""
        tok = self.tokens[self.pos]
        if tok.type != TokenType.EOF:
            self.pos += 1
        return tok
    
    def _consume(self, expected: TokenType, msg: str) -> Token:
        """Ensure current token is `expected`, else raise ParseError"""
        if self._current().type == expected:
            return self._advance()
        raise ParseError(f"Expected {expected}, got {self._current()}")
    
    def expr(self) -> ASTNode:
        """expr → term (('+' | '-') term)*"""
        left = self.term()  # Parse first term
        
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op = self._current().value  # '+' or '-'
            self._advance()
            right = self.term()  # Parse next term
            left = BinOp(left, op, right)  # Combine: left OP right
        
        return left
    
    def term(self) -> ASTNode:
        """term → factor (('*' | '/') factor)*"""
        left = self.factor()
        
        while self._check(TokenType.MULTIPLY, TokenType.DIVIDE):
            op = self._current().value
            self._advance()
            right = self.factor()
            left = BinOp(left, op, right)
        
        return left
    
    def factor(self) -> ASTNode:
        """factor → NUMBER | IDENTIFIER | '(' expr ')'"""
        if self._check(TokenType.NUMBER):
            value = float(self._current().value)
            self._advance()
            return Number(value)
        
        elif self._check(TokenType.IDENTIFIER):
            name = self._current().value
            self._advance()
            return Identifier(name)
        
        elif self._check(TokenType.LPAREN):
            self._advance()  # consume '('
            expr = self.expr()  # recursively parse expression inside parens
            self._consume(TokenType.RPAREN, "Expected ')'")
            return expr
        
        else:
            raise ParseError(f"Unexpected token: {self._current()}")
```

### Hardcoded vs Dynamic

| Aspect | Type | Details |
|--------|------|---------|
| **Grammar rules** | HARDCODED | `expr → term (('+' | '-') term)*` structure |
| **Operator precedence** | HARDCODED | `*` / `/` bind tighter than `+` / `-` |
| **Associativity** | HARDCODED | All operators are left-associative |
| **Token consumption** | HARDCODED | Always left-to-right, one token lookahead |
| **Token stream** | DYNAMIC | Input from lexer |
| **AST structure** | DYNAMIC | Built from tokens according to grammar |

---

## PHASE 3: SEMANTIC ANALYSIS (Evaluation)

**File:** `compiler/semantic.py`

**Task:** Walk the AST, check semantic rules, evaluate expressions to values

### Semantic Rules (HARDCODED)

```python
# Three checks performed:
1. Undefined variable:  can't use a variable before it's assigned
2. Division by zero:    divisor must not be 0
3. Type consistency:    operands of arithmetic operators must be numeric
```

### Example: Evaluate `"x = 10; y = x + 5"`

**Input AST:**
```
Program
├── Assign(name='x', value=Number(10))
└── Assign(name='y', value=BinOp(Identifier('x'), '+', Number(5)))
```

**Walkthrough:**

```python
# Start with global scope
scopes = [{}]  # Empty global symbol table

# Process statement 1: Assign('x', Number(10))
# → Evaluate Number(10) → 10
# → Declare x = 10 in global scope
scopes = [{'x': 10}]
result_1 = 10

# Process statement 2: Assign('y', BinOp(Identifier('x'), '+', Number(5)))
# → Evaluate Identifier('x')
#   → Resolve 'x' in scopes (found in global scope)
#   → Returns 10
# → Evaluate Number(5)
#   → Returns 5
# → Evaluate BinOp(10, '+', 5)
#   → Returns 10 + 5 = 15
# → Declare y = 15 in global scope
scopes = [{'x': 10, 'y': 15}]
result_2 = 15

# Output:
# Symbol table = {'x': 10, 'y': 15}
# Evaluation results = [10, 15]
```

### Code Structure

```python
class SemanticAnalyzer:
    def __init__(self):
        # Start with one global scope
        self.scopes = [{}]  # List of dicts, innermost is -1
    
    def _resolve(self, name: str) -> int | float:
        """Look up variable in scopes (innermost to outermost)"""
        # Walk scopes backwards: local scope last, global scope first
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        # Not found in any scope → ERROR
        raise SemanticError(f"Undefined variable '{name}'")
    
    def _declare(self, name: str, value: int | float) -> None:
        """Store variable in current (innermost) scope"""
        self.scopes[-1][name] = value
    
    def analyze(self, node: ASTNode) -> Any:
        """Recursively analyze and evaluate node"""
        if isinstance(node, Program):
            # Evaluate each statement
            results = []
            for stmt in node.statements:
                result = self.analyze(stmt)
                results.append(result)
            return results
        
        elif isinstance(node, Assign):
            # Evaluate the right-hand side
            value = self.analyze(node.value)
            # Store in symbol table
            self._declare(node.name, value)
            # Assignments return their value
            return value
        
        elif isinstance(node, BinOp):
            # Evaluate both operands
            left = self.analyze(node.left)
            right = self.analyze(node.right)
            
            # Apply operator
            if node.op == '+':
                return left + right
            elif node.op == '-':
                return left - right
            elif node.op == '*':
                return left * right
            elif node.op == '/':
                if right == 0:
                    raise SemanticError("Division by zero")
                return left / right
        
        elif isinstance(node, Identifier):
            # Look up variable
            return self._resolve(node.name)
        
        elif isinstance(node, Number):
            # Return the numeric value
            return node.value
        
        elif isinstance(node, PrintStmt):
            # Evaluate the expression and print it
            value = self.analyze(node.expression)
            print(f"  [print] {value}")
            return None
```

### Hardcoded vs Dynamic

| Aspect | Type | Details |
|--------|------|---------|
| **Semantic rules** | HARDCODED | 3 rules: undefined var, div by zero, type check |
| **Scope management** | HARDCODED | Stack of dicts, reversed lookup |
| **Variable lookup order** | HARDCODED | Innermost scope first (local shadowing) |
| **Operator implementations** | HARDCODED | `+`, `-`, `*`, `/` operations |
| **Symbol table** | DYNAMIC | Built during evaluation |
| **Expression values** | DYNAMIC | Computed from AST and input |

---

## AST Node Types

**File:** `compiler/ast_nodes.py`

**Purpose:** Define the structure of the Abstract Syntax Tree

### Node Types (HARDCODED)

```python
@dataclass(frozen=True, slots=True)
class Program(ASTNode):
    """Root node"""
    statements: tuple[ASTNode, ...]

@dataclass(frozen=True, slots=True)
class Assign(ASTNode):
    """Variable assignment: name = value"""
    name: str
    value: ASTNode

@dataclass(frozen=True, slots=True)
class BinOp(ASTNode):
    """Binary operator: left OP right"""
    left: ASTNode
    op: str  # '+', '-', '*', '/'
    right: ASTNode

@dataclass(frozen=True, slots=True)
class Number(ASTNode):
    """Numeric literal"""
    value: int | float

@dataclass(frozen=True, slots=True)
class Identifier(ASTNode):
    """Variable reference"""
    name: str

@dataclass(frozen=True, slots=True)
class PrintStmt(ASTNode):
    """print(expr) statement"""
    expression: ASTNode
```

### Why Frozen + Slots?

```python
frozen=True   # Immutable — once created, cannot be modified
              # (good for AST which is built once, read many times)

slots=True    # Memory efficient — nodes don't have __dict__
              # (good for large trees with many nodes)
```

---

## OUTPUT GENERATION

### Option 1: Console Output (Terminal)

**File:** `compiler/pipeline.py`

Called by `compile_source()`, prints to stdout:

```
================================================================
  FRONT-END COMPILER
  Parser : Recursive Descent  (top-down, LL(1))
================================================================
  Input  : "x = 10; y = x + 5"

──────────────────────────────────────────────────────────────
  PHASE 1 · LEXICAL ANALYSIS
──────────────────────────────────────────────────────────────
  ...tokens listed...
  ✓ 9 token(s) produced.

──────────────────────────────────────────────────────────────
  PHASE 2 · SYNTAX ANALYSIS
──────────────────────────────────────────────────────────────
  ...AST tree...
  ✓ AST built successfully.

──────────────────────────────────────────────────────────────
  PHASE 3 · SEMANTIC ANALYSIS
──────────────────────────────────────────────────────────────
  Symbol table (global scope):
    x  =  10
    y  =  15
  
  Evaluation results:
    statement 1  →  10
    statement 2  →  15
  ✓ Semantic analysis passed.
================================================================
```

### Option 2: HTML Report (Browser)

**File:** `compiler/report.py`

Creates `compiler_report.html` with:
- Tabbed interface for each test case
- Grammar tables (FIRST, FOLLOW, LL(1) table)
- Precedence tables
- All three phases for each case
- Parse step-by-step trace
- Visual SVG AST diagrams

---

## Complete Input-to-Output Example

### Input
```
x = 10; y = x + 5
```

### Step 1: Lexical Analysis (Lexer)

```
"x = 10; y = x + 5"
         ↓
Token stream:
[
  Token(IDENTIFIER, 'x', 1, 1),
  Token(ASSIGN, '=', 1, 3),
  Token(NUMBER, '10', 1, 5),
  Token(SEMICOLON, ';', 1, 7),
  Token(IDENTIFIER, 'y', 1, 9),
  Token(ASSIGN, '=', 1, 11),
  Token(IDENTIFIER, 'x', 1, 13),
  Token(PLUS, '+', 1, 15),
  Token(NUMBER, '5', 1, 17),
  Token(EOF, '', 1, 18)
]
```

### Step 2: Syntax Analysis (Parser)

```
Token stream
           ↓
         parse()
         ├─ statement()
         │  ├─ Assign('x', Number(10))  ← "x = 10"
         │  └─ Assign('y', BinOp(...))  ← "y = x + 5"
         ↓
AST:
Program(
  statements=(
    Assign(name='x', value=Number(10)),
    Assign(name='y', value=BinOp(
      left=Identifier('x'),
      op='+',
      right=Number(5)
    ))
  )
)
```

### Step 3: Semantic Analysis

```
AST
 ↓
analyze(Program(...))
├─ analyze(Assign('x', Number(10)))
│  ├─ analyze(Number(10)) → 10
│  └─ _declare('x', 10)
│  └─ return 10
│
└─ analyze(Assign('y', BinOp(...)))
   ├─ analyze(BinOp(Identifier('x'), '+', Number(5)))
   │  ├─ analyze(Identifier('x')) → _resolve('x') → 10
   │  ├─ analyze(Number(5)) → 5
   │  └─ 10 + 5 = 15
   └─ _declare('y', 15)
   └─ return 15

 ↓
Output:
{
  symbol_table: {'x': 10, 'y': 15},
  eval_results: [10, 15],
  errors: []
}
```

### Step 4: Report Generation

```python
# HTML file with all three phases displayed
compiler_report.html
├─ Header: "x = 10; y = x + 5  (Recursive Descent parser)"
├─ Phase 1 section:
│  ├─ Tokens table
│  └─ "✓ 9 tokens produced"
├─ Phase 2 section:
│  ├─ AST tree
│  └─ "✓ AST built successfully"
└─ Phase 3 section:
   ├─ Symbol table: {x: 10, y: 15}
   ├─ Eval results: [10, 15]
   └─ "✓ Semantic analysis passed"
```

---

## Hardcoded vs Dynamic Summary

### HARDCODED (Fixed by Language Design)

| Component | What's Hardcoded |
|-----------|-----------------|
| **Lexer** | Regex patterns for numbers, identifiers, operators |
| **Parser** | Grammar rules; precedence (expr → term → factor) |
| **Semantic Analyzer** | Semantic rules; variable lookup algorithm |
| **Operator Set** | Only `+`, `-`, `*`, `/`, `=`, `;`, `()` |
| **Node Types** | Program, Assign, BinOp, Number, Identifier, PrintStmt |
| **Comment Syntax** | `//` for comments |
| **Scope Rules** | Variable shadowing (inner scope hides outer scope) |
| **Error Checks** | 3 semantic checks: undefined var, div by zero, type |

### DYNAMIC (Depends on Input)

| Component | What's Dynamic |
|-----------|----------------|
| **Input** | Any string with numbers, variables, operators |
| **Token Stream** | Generated from input |
| **AST** | Shaped by token stream and grammar rules |
| **Symbol Table** | Built during semantic analysis (variable values) |
| **Evaluation Results** | Computed from AST |
| **Errors** | Found in any phase if input violates rules |
| **Console Output** | Formatted phase-by-phase |
| **HTML Report** | Generated with actual data from run |

---

## Error Handling Flow

```
Error Type          Where Caught        What Happens
─────────────────────────────────────────────────────
Invalid character   Lexer              Collected in errors list
Syntax error        Parser             ParseError raised, compilation halts
Undefined variable  Semantic Analyzer  SemanticError raised
Division by zero    Semantic Analyzer  SemanticError raised
Type error          Semantic Analyzer  SemanticError raised (impl. dependent)
```

Each error includes:
- **Message:** What went wrong
- **Line:** Where in source
- **Column:** Position in line

---

## Files & Their Responsibilities

```
main.py
├─ Entry point
├─ Command-line parsing (--both, --bottom-up, --visual)
└─ Calls compile_source() and generate_report()

compiler/
├─ pipeline.py          ← Orchestrates all three phases
├─ lexer.py             ← Phase 1: Tokenization
├─ parser.py            ← Phase 2a: Top-down parsing (LL(1))
├─ bottom_up_parser.py  ← Phase 2b: Bottom-up parsing (shift-reduce)
├─ semantic.py          ← Phase 3: Semantic analysis & evaluation
├─ ast_nodes.py         ← AST node definitions + pretty-printer
├─ tokens.py            ← Token type enums
├─ visualizer.py        ← SVG AST visualization
└─ report.py            ← HTML report generation
```

---

## Summary

1. **Lexer** breaks input string into tokens using hardcoded regex patterns
2. **Parser** builds AST from tokens using hardcoded grammar rules
3. **Semantic Analyzer** evaluates AST and checks hardcoded semantic rules
4. **Report Generator** produces human-readable output (console or HTML)

The **grammar, precedence, and semantic rules are all hardcoded** by design (they define the language).  
The **token stream, AST, and results are all dynamic** (they depend on input).
