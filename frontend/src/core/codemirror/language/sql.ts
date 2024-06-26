/* Copyright 2024 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { sql, StandardSQL, schemaCompletionSource } from "@codemirror/lang-sql";
import dedent from "string-dedent";
import { CompletionConfig } from "@/core/config/config-schema";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { indentOneTab } from "./utils/indentOneTab";
import { autocompletion, CompletionSource } from "@codemirror/autocomplete";
import { store } from "@/core/state/jotai";
import { datasetsAtom } from "@/core/datasets/state";
import { QUOTE_PREFIX_KINDS, QuotePrefixKind, splitQuotePrefix, upgradePrefixKind } from "./utils/quotes";

// TODO: force one?
const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ["'", "'"],
  ['"', '"'],
];

// explode into all combinations
const pairs = QUOTE_PREFIX_KINDS.flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end]),
);

const regexes = pairs.map(
  ([start, end]) =>
    // mo.sql( + any number of spaces + start + capture + any number of spaces + end)
    [
      start,
      new RegExp(`^mo\\.sql\\(\\s*${start}(.*)${end}\\s*\\)$`, "s"),
    ] as const,
);

/**
 * Language adapter for SQL.
 */
export class SQLLanguageAdapter implements LanguageAdapter {
  type = "sql" as const;

  lastQuotePrefix: QuotePrefixKind = "";

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];

        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        // store the quote prefix for later when we transform out
        this.lastQuotePrefix = quotePrefix;
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
    const start = `mo.sql(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', '\\"""');
    const end = `\n    """\n)`;
    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "") {
      return true;
    }

    if (pythonCode.trim() === "mo.sql()") {
      return true;
    }

    const lines = pythonCode
      .trim()
      .split("\n")
      .map((line) => line.startsWith("mo.sql("))
      .filter(Boolean);
    if (lines.length > 1) {
      // more than line starting with mo.sql(; as a heuristic,
      // don't show "view as sql"
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
    const schema: Record<string, string[]> = {}
    const datasets = store.get(datasetsAtom)
    for (const table of datasets.tables) {
      schema[table.name] = table.columns.map((column) => column.name)
    }

    return schemaCompletionSource({
      schema
    })(ctx)
  }
}
