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

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ["'", "'"],
  ['"', '"'],
];

// explode into all combinations
// only f is supported
const pairs = QUOTE_PREFIX_KINDS.flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end]),
);

const regexes = pairs.map(
  ([start, end]) =>
    // df = mo.sql( space + start + capture + space + end, optional output flag)
    [
      start,
      new RegExp(
        `^(?<dataframe>\\w*)\\s*=\\s*mo\\.sql\\(\\s*${start}(?<sql>.*)${end}\\s*(?:,\\s*output\\s*=\\s*(?<output>True|False),?)?\\s*\\)$`,
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

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
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

        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        // store the quote prefix for later when we transform out
        this.lastQuotePrefix = quotePrefix;
        this.dataframeName = dataframe;
        this.showOutput = output === undefined ? true : output === "True";
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
    const end = `\n    """${this.showOutput ? "" : ", output=False"}\n)`;
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
