/**
 * compiler/pipeline.ts
 * ─────────────────────────────────────────────────────────────
 * Unified front-end compiler pipeline with enhanced error reporting.
 */

import { formatAST } from "./ast_nodes";
import { BottomUpParser, BottomUpParseError, PRECEDENCE } from "./bottom_up_parser";
import { Lexer, formatTokens, RE1_NUMBER_STR, RE2_IDENTIFIER_STR, RE3_OPERATOR_STR } from "./lexer";
import { Parser, ParseError } from "./parser";
import { SemanticAnalyzer, SemanticError } from "./semantic";
import { TokenType } from "./tokens";

const BAR = "=".repeat(64);
const DASH = "─".repeat(64);
const TICK = "  ✓";
const CROSS = "  ✗";

function formatErrorWithContext(
  message: string,
  source: string,
  line?: number,
  column?: number
): string {
  let errorStr = message;

  if (line !== undefined && column !== undefined) {
    errorStr += ` at line ${line}, column ${column}`;

    const sourceLines = source.split("\n");
    if (line > 0 && line <= sourceLines.length) {
      const sourceLine = sourceLines[line - 1];
      errorStr += `\n    ${sourceLine}\n    ${" ".repeat(column - 1)}^`;
    }
  } else if (line !== undefined) {
    errorStr += ` at line ${line}`;
  }

  return errorStr;
}

export function compileSource(source: string, useBottomUp: boolean = false): void {
  const parserName = useBottomUp
    ? "Shift-Reduce  (bottom-up, operator-precedence)"
    : "Recursive Descent  (top-down, LL(1))";

  console.log(BAR);
  console.log("  FRONT-END COMPILER");
  console.log(`  Parser : ${parserName}`);
  console.log(BAR);
  console.log(`  Input  : ${JSON.stringify(source)}`);
  console.log();

  // ═══════════════════════════════════════════════════════
  // PHASE 1 — LEXICAL ANALYSIS
  // ═══════════════════════════════════════════════════════
  console.log(DASH);
  console.log("  PHASE 1 · LEXICAL ANALYSIS");
  console.log(DASH);
  console.log(`  RE1 (numbers)     :  ${RE1_NUMBER_STR}`);
  console.log(`  RE2 (identifiers) :  ${RE2_IDENTIFIER_STR}`);
  console.log(`  RE3 (operators)   :  ${RE3_OPERATOR_STR}`);
  console.log(
    "  Master pattern    :  RE1 | RE2 | RE3  (comments & whitespace stripped)"
  );
  console.log();

  const [tokens, lexErrors] = new Lexer(source).tokenize();

  if (lexErrors.length > 0) {
    for (const err of lexErrors) {
      const formatted = formatErrorWithContext(
        err.message,
        source,
        err.line,
        err.column
      );
      console.log(`${CROSS} ${formatted}`);
    }
    console.log();
    console.log("  Lexical errors found — compilation halted.");
    console.log(BAR);
    return;
  }

  console.log(formatTokens(tokens));
  console.log();
  const nonEof = tokens.filter((t) => t.type !== TokenType.EOF);
  console.log(`${TICK} ${nonEof.length} token(s) produced.`);
  console.log();

  // ═══════════════════════════════════════════════════════
  // PHASE 2 — SYNTAX ANALYSIS
  // ═══════════════════════════════════════════════════════
  console.log(DASH);
  console.log("  PHASE 2 · SYNTAX ANALYSIS");
  console.log(DASH);
  console.log(`  Parser        : ${parserName}`);
  console.log("  Associativity : Left-to-right for all binary operators");
  console.log(
    "  Precedence    : +/-  <  */  <  ()  <  atoms  (low → high)"
  );

  if (useBottomUp) {
    const prec = Object.entries(PRECEDENCE)
      .map(([tt, p]) => `${tt}=${p}`)
      .join("  |  ");
    console.log(`  Prec. table   : ${prec}`);
  }
  console.log();

  let ast;
  let parseSteps: string[] = [];

  try {
    if (useBottomUp) {
      const parser = new BottomUpParser(tokens);
      ast = parser.parse();
      parseSteps = parser.steps;
    } else {
      const parser = new Parser(tokens);
      ast = parser.parse();
      parseSteps = parser.steps;
    }
  } catch (err) {
    if (err instanceof ParseError || err instanceof BottomUpParseError) {
      const formatted = formatErrorWithContext(
        (err as any).message,
        source,
        (err as any).line,
        (err as any).column
      );
      console.log(`${CROSS} ${formatted}`);
    } else {
      console.log(`${CROSS} ${String(err)}`);
    }
    console.log();
    console.log("  Parse steps:");
    for (const step of parseSteps) {
      console.log(`    ${step}`);
    }
    console.log();
    console.log("  Parsing halted.");
    console.log(BAR);
    return;
  }

  console.log("  Parse steps:");
  for (const step of parseSteps) {
    console.log(`    ${step}`);
  }
  console.log();
  console.log(`${TICK} AST built.`);
  console.log();

  // ═══════════════════════════════════════════════════════
  // PHASE 3 — SEMANTIC ANALYSIS
  // ═══════════════════════════════════════════════════════
  console.log(DASH);
  console.log("  PHASE 3 · SEMANTIC ANALYSIS");
  console.log(DASH);
  console.log("  Checks : undefined variables  |  division by zero  |  type consistency");
  console.log("  Scopes : push on block entry, pop on block exit  (variable shadowing)");
  console.log();

  try {
    const analyzer = new SemanticAnalyzer();
    const results = analyzer.analyze(ast);

    console.log(
      "Symbol table (global scope):"
    );
    const symTable = analyzer.symbolTable;
    const entries = Object.entries(symTable);
    if (entries.length === 0) {
      console.log("  (empty)");
    } else {
      for (const [name, value] of entries) {
        console.log(`  ${name} = ${value}`);
      }
    }
    console.log();

    const nonNullResults = results.filter((r: any) => r !== null);
    console.log(
      `${TICK} Type-checked and evaluated. Results: [${nonNullResults.join(", ")}]`
    );
  } catch (err) {
    if (err instanceof SemanticError) {
      const formatted = formatErrorWithContext(
        err.message,
        source,
        err.line,
        err.column
      );
      console.log(`${CROSS} ${formatted}`);
    } else {
      console.log(`${CROSS} ${String(err)}`);
    }
    console.log();
    console.log("  Semantic analysis halted.");
    console.log(BAR);
    return;
  }

  console.log();
  console.log("  AST:");
  console.log();
  const astStr = formatAST(ast);
  for (const line of astStr.split("\n")) {
    console.log(`    ${line}`);
  }

  console.log();
  console.log(BAR);
}
