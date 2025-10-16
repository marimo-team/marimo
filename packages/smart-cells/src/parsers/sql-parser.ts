/* Copyright 2024 Marimo. All rights reserved. */

import type { SyntaxNode, TreeCursor } from "@lezer/common";
import dedent from "string-dedent";
import type {
  FormatResult,
  LanguageParser,
  ParseResult,
  QuotePrefixKind,
} from "../types.js";
import {
  getPrefixLength,
  getStringContent,
  parseArgsKwargs,
  parsePythonAST,
  safeDedent,
} from "../utils/index.js";

export interface SQLMetadata {
  dataframeName: string;
  quotePrefix: QuotePrefixKind;
  commentLines: string[];
  showOutput: boolean;
  engine: string;
}

const DEFAULT_ENGINE = "__marimo_duckdb";

interface SQLParseInfo {
  dfName: string;
  sqlString: string;
  engine: string | undefined;
  output: boolean | undefined;
  startPosition: number;
}

/**
 * Parser for marimo SQL cells (mo.sql()).
 *
 * Converts between Python code like `_df = mo.sql(f"""SELECT * FROM users""")` and
 * plain SQL like `SELECT * FROM users`.
 */
export class SQLParser implements LanguageParser<SQLMetadata> {
  readonly type = "sql";

  readonly defaultMetadata: SQLMetadata = {
    dataframeName: "_df",
    quotePrefix: "f",
    commentLines: [],
    showOutput: true,
    engine: DEFAULT_ENGINE,
  };

  get defaultCode(): string {
    return `_df = mo.sql(f"""SELECT * FROM """)`;
  }

  /**
   * Create a SQL cell from a SQL query.
   */
  static fromQuery(query: string): string {
    return `_df = mo.sql(f"""${query.trim()}""")`;
  }

  transformIn(pythonCode: string): ParseResult<SQLMetadata> {
    pythonCode = pythonCode.trim();

    // Default metadata
    const metadata: SQLMetadata = {
      ...this.defaultMetadata,
      commentLines: this.extractCommentLines(pythonCode),
    };

    if (!this.isSupported(pythonCode)) {
      // Just return the original code if not supported
      return { code: pythonCode, offset: 0, metadata };
    }

    // Handle empty strings
    if (pythonCode === "") {
      return { code: "", offset: 0, metadata };
    }

    const sqlStatement = parseSQLStatement(pythonCode);
    if (sqlStatement) {
      metadata.dataframeName = sqlStatement.dfName;
      metadata.showOutput = sqlStatement.output ?? true;
      metadata.engine = sqlStatement.engine ?? DEFAULT_ENGINE;

      return {
        code: dedent(`\n${sqlStatement.sqlString}\n`).trim(),
        offset: sqlStatement.startPosition,
        metadata,
      };
    }

    return { code: pythonCode, offset: 0, metadata };
  }

  transformOut(code: string, metadata: SQLMetadata): FormatResult {
    const { quotePrefix, commentLines, showOutput, engine, dataframeName } =
      metadata;

    const start = `${dataframeName} = mo.sql(\n    ${quotePrefix}"""\n`;
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    const showOutputParam = showOutput ? "" : ",\n    output=False";
    const engineParam =
      engine === DEFAULT_ENGINE ? "" : `,\n    engine=${engine}`;
    const end = `\n    """${showOutputParam}${engineParam}\n)`;

    return {
      code:
        [...commentLines, start].join("\n") + indentOneTab(escapedCode) + end,
      offset: start.length + 1,
    };
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "") {
      return true;
    }

    // Has at least one `mo.sql` call
    if (!pythonCode.includes("mo.sql")) {
      return false;
    }

    // Does not have 2 `mo.sql` calls
    if (pythonCode.split("mo.sql").length > 2) {
      return false;
    }

    return parseSQLStatement(pythonCode) !== null;
  }

  private extractCommentLines(pythonCode: string): string[] {
    const lines = pythonCode.split("\n");
    const commentLines: string[] = [];
    for (const line of lines) {
      if (line?.startsWith("#")) {
        commentLines.push(line);
      } else {
        break;
      }
    }
    return commentLines;
  }
}

/**
 * Find an assignment node that is preceded only by comments.
 */
function findAssignment(cursor: TreeCursor): SyntaxNode | null {
  do {
    if (cursor.name === "AssignStatement") {
      return cursor.node;
    }

    if (cursor.name !== "Comment") {
      return null;
    }
  } while (cursor.next());
  return null;
}

/**
 * Parse a SQL statement from a Python code string.
 *
 * @param code - The Python code string to parse
 * @returns The parsed SQL statement or null if parsing fails
 */
function parseSQLStatement(code: string): SQLParseInfo | null {
  try {
    const tree = parsePythonAST(code);
    const cursor = tree.cursor();

    // Trees start with a Script node
    if (cursor.name === "Script") {
      cursor.next();
    }
    const assignStmt = findAssignment(cursor);
    if (!assignStmt) {
      return null;
    }

    // Code after the assignment statement is not allowed
    if (code.slice(assignStmt.to).trim().length > 0) {
      return null;
    }

    let dfName: string | null = null;
    let sqlString: string | null = null;
    let engine: string | undefined;
    let output: boolean | undefined;
    let startPosition = 0;

    // Parse the assignment
    const assignCursor = assignStmt.cursor();
    assignCursor.firstChild(); // Move to first child of assignment

    // First child should be the variable name
    if (assignCursor.name === "VariableName") {
      dfName = code.slice(assignCursor.from, assignCursor.to);
    }

    if (!dfName) {
      return null;
    }

    // Move to the expression part (after the =)
    while (assignCursor.next()) {
      if (assignCursor.name === "CallExpression") {
        // Check if it's mo.sql call
        const callCursor = assignCursor.node.cursor();
        let isMoSql = false;

        callCursor.firstChild(); // Move to first child of call
        if (callCursor.name === "MemberExpression") {
          const memberText = code.slice(callCursor.from, callCursor.to);
          isMoSql = memberText === "mo.sql";
        }

        if (!isMoSql) {
          return null;
        }

        // Move to arguments
        while (callCursor.next()) {
          if (callCursor.name === "ArgList") {
            const argListCursor = callCursor.node.cursor();

            const { args, kwargs } = parseArgsKwargs(argListCursor, code);

            // Parse positional args (SQL query)
            if (args.length === 1) {
              sqlString = getStringContent(args[0], code);
              startPosition =
                args[0].from +
                getPrefixLength(code.slice(args[0].from, args[0].to));
            }

            // Parse kwargs (engine and output)
            for (const { key, value } of kwargs) {
              switch (key) {
                case "engine":
                  engine = value;
                  break;
                case "output":
                  output = value === "True";
                  break;
              }
            }

            // Check if sql string is empty
            if (sqlString === "") {
              return { dfName, sqlString: "", engine, output, startPosition };
            }

            break;
          }
        }
      }
    }

    if (!dfName || !sqlString) {
      return null;
    }

    return {
      dfName,
      sqlString: safeDedent(sqlString),
      engine,
      output,
      startPosition,
    };
  } catch (error) {
    // biome-ignore lint/suspicious/noConsole: warning ok
    console.warn("Failed to parse SQL statement", error);
    return null;
  }
}

/**
 * Indent code by one tab (4 spaces).
 */
function indentOneTab(code: string): string {
  return code
    .split("\n")
    .map((line) => (line?.trim() ? `    ${line}` : line))
    .join("\n");
}
