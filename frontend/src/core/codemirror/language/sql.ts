/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import type { LanguageAdapter } from "./types";
import { sql, StandardSQL, schemaCompletionSource } from "@codemirror/lang-sql";
import dedent from "string-dedent";
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { indentOneTab } from "./utils/indentOneTab";
import {
  autocompletion,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { store } from "@/core/state/jotai";
import { datasetsAtom } from "@/core/datasets/state";
import { type QuotePrefixKind, upgradePrefixKind } from "./utils/quotes";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { MarkdownLanguageAdapter } from "./markdown";
import type { ConnectionName } from "@/core/cells/data-source-connections";
import { atom } from "jotai";
import { parser } from "@lezer/python";
import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { parseArgsKwargs } from "./utils/ast";

// Default engine to use when not specified, shouldn't conflict with user_defined engines
export const DEFAULT_ENGINE: ConnectionName =
  "_marimo_duckdb" as ConnectionName;

export const latestEngineSelected = atom<ConnectionName>(DEFAULT_ENGINE);

/**
 * Language adapter for SQL.
 */
export class SQLLanguageAdapter implements LanguageAdapter {
  readonly type = "sql";
  readonly defaultCode = `_df = mo.sql(f"""SELECT * FROM """)`;
  static fromQuery = (query: string) => `_df = mo.sql(f"""${query.trim()}""")`;

  dataframeName = "_df";
  lastQuotePrefix: QuotePrefixKind = "f";
  showOutput = true;
  engine: ConnectionName = store.get(latestEngineSelected);

  getDefaultCode(): string {
    if (this.engine === DEFAULT_ENGINE) {
      return `_df = mo.sql(f"""SELECT * FROM """)`;
    }
    return `_df = mo.sql(f"""SELECT * FROM """, engine=${this.engine})`;
  }

  transformIn(
    pythonCode: string,
  ): [sqlQuery: string, queryStartOffset: number] {
    if (!this.isSupported(pythonCode)) {
      // Attempt to remove any markdown wrappers
      const [transformedCode, offset] =
        new MarkdownLanguageAdapter().transformIn(pythonCode);
      // Just return the original code
      return [transformedCode, offset];
    }

    pythonCode = pythonCode.trim();

    // Handle empty strings
    if (pythonCode === "") {
      this.lastQuotePrefix = "f";
      this.showOutput = true;
      return ["", 0];
    }

    const sqlStatement = parseSQLStatement(pythonCode);
    if (sqlStatement) {
      this.dataframeName = sqlStatement.dfName;
      this.showOutput = sqlStatement.output ?? true;
      this.engine = (sqlStatement.engine as ConnectionName) ?? DEFAULT_ENGINE;

      if (this.engine !== DEFAULT_ENGINE) {
        // User selected a new engine, set it as latest.
        // This makes new SQL statements use the new engine by default.
        store.set(latestEngineSelected, this.engine);
      }

      return [
        dedent(`\n${sqlStatement.sqlString}\n`).trim(),
        sqlStatement.startPosition,
      ];
    }

    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    // Get the quote type from the last transformIn
    const prefix = upgradePrefixKind(this.lastQuotePrefix, code);

    // Multiline code
    const start = `${this.dataframeName} = mo.sql(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    const showOutputParam = this.showOutput ? "" : ",\n    output=False";
    const engineParam =
      this.engine === DEFAULT_ENGINE ? "" : `,\n    engine=${this.engine}`;
    const end = `\n    """${showOutputParam}${engineParam}\n)`;

    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    const sqlCapabilities = store.get(capabilitiesAtom).sql;
    if (!sqlCapabilities) {
      return false;
    }

    if (pythonCode.trim() === "") {
      return true;
    }

    // Does not have 2 `mo.sql` calls
    if (pythonCode.split("mo.sql").length > 2) {
      return false;
    }

    // Has at least one `mo.sql` call
    if (!pythonCode.includes("mo.sql")) {
      return false;
    }

    return parseSQLStatement(pythonCode) !== null;
  }

  selectEngine(connectionName: ConnectionName): void {
    this.engine = connectionName;
    store.set(latestEngineSelected, connectionName);
  }

  setShowOutput(showOutput: boolean): void {
    this.showOutput = showOutput;
  }

  getExtension(
    _completionConfig: CompletionConfig,
    _hotkeys: HotkeyProvider,
  ): Extension[] {
    return [
      sql({
        dialect: StandardSQL,
      }),
      autocompletion({
        activateOnTyping: true,
      }),
      StandardSQL.language.data.of({
        autocomplete: tablesCompletionSource(),
      }),
    ];
  }
}

function tablesCompletionSource(): CompletionSource {
  return (ctx) => {
    const schema: Record<string, string[]> = {};
    const datasets = store.get(datasetsAtom);
    for (const table of datasets.tables) {
      schema[table.name] = table.columns.map((column) => column.name);
    }

    return schemaCompletionSource({
      schema,
    })(ctx);
  };
}

interface SQLConfig {
  dfName: string;
  sqlString: string;
  engine: string | undefined;
  output: boolean | undefined;
  startPosition: number;
}

function findAssignment(cursor: TreeCursor): SyntaxNode | null {
  do {
    if (cursor.name === "AssignStatement") {
      return cursor.node;
    }
  } while (cursor.next());
  return null;
}

function getStringContent(node: SyntaxNode, code: string): string | null {
  // Handle triple quoted strings
  if (node.name === "String") {
    const content = code.slice(node.from, node.to);
    // Remove quotes and trim
    if (content.startsWith('"""') || content.startsWith("'''")) {
      return content.slice(3, -3).trim();
    }
    // Handle single quoted strings
    return content.slice(1, -1).trim();
  }
  // Handle f-strings
  if (node.name === "FString" || node.name === "FormatString") {
    // Replace formatted values with 'null' as per test cases
    let result = "";
    const cursor = node.cursor();
    do {
      if (cursor.name === "StringContent") {
        result += code.slice(cursor.from, cursor.to);
      } else if (cursor.name === "FormattedValue") {
        result += "null";
      }
    } while (cursor.next());
    return result.trim();
  }
  return null;
}

/**
 * Parses a SQL statement from a Python code string.
 *
 * @param code - The Python code string to parse.
 * @returns The parsed SQL statement or null if parsing fails.
 */
export function parseSQLStatement(code: string): SQLConfig | null {
  try {
    const tree = parser.parse(code.trim());
    const cursor = tree.cursor();

    // Find assignment statement
    const assignStmt = findAssignment(cursor);
    if (!assignStmt) {
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
      sqlString,
      engine,
      output,
      startPosition,
    };
  } catch (e) {
    return null;
  }
}

function getPrefixLength(code: string): number {
  if (code === "") {
    return 0;
  }
  if (code.startsWith('f"""') || code.startsWith("f'''")) {
    return 4;
  }
  if (code.startsWith('"""') || code.startsWith("'''")) {
    return 3;
  }
  if (code.startsWith("f'") || code.startsWith('f"')) {
    return 2;
  }
  if (code.startsWith("'") || code.startsWith('"')) {
    return 1;
  }
  return 0;
}
