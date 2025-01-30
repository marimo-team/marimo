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
import {
  QUOTE_PREFIX_KINDS,
  type QuotePrefixKind,
  splitQuotePrefix,
  upgradePrefixKind,
} from "./utils/quotes";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { MarkdownLanguageAdapter } from "./markdown";
import type { ConnectionName } from "@/core/cells/data-source-connections";

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ["'", "'"],
  ['"', '"'],
];

// Default engine to use when not specified, shouldn't conflict with user_defined engines
export const DEFAULT_ENGINE: ConnectionName =
  "_marimo_duckdb" as ConnectionName;

// explode into all combinations
// only f is supported
const pairs = QUOTE_PREFIX_KINDS.flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end]),
);

const regexes = pairs.map(
  ([start, end]) =>
    // df = mo.sql( space + start + capture + space + end, optional output flag, optional engine param)
    [
      start,
      new RegExp(
        `^(?<dataframe>\\w*)\\s*=\\s*mo\\.sql\\(\\s*${start}(?<sql>.*)${end}\\s*(?:(?:,\\s*output\\s*=\\s*(?<output>True|False))?,?(?:,\\s*engine\\s*=\\s*(?<engine>\\w+))?)?,?\\s*\\)$`,
        "s",
      ),
    ] as const,
);

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
  engine: ConnectionName = DEFAULT_ENGINE;

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

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const dataframe = match.groups?.dataframe || this.dataframeName;
        const innerCode = match.groups?.sql || "";
        const output = match.groups?.output;
        const engine = match.groups?.engine;

        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        // store the quote prefix for later when we transform out
        this.lastQuotePrefix = quotePrefix;
        this.dataframeName = dataframe;
        this.showOutput = output === undefined ? true : output === "True";
        this.engine =
          engine === undefined ? DEFAULT_ENGINE : (engine as ConnectionName);
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        // string-dedent expects the first and last line to be empty / contain only whitespace, so we pad with \n
        return [dedent(`\n${unescapedCode}\n`).trim(), offset];
      }
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

    // not 2 mo.sql calls
    if (pythonCode.split("mo.sql").length > 2) {
      return false;
    }

    return regexes.some(([, regex]) => regex.test(pythonCode));
  }

  selectEngine(connectionName: ConnectionName): void {
    this.engine = connectionName;
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
