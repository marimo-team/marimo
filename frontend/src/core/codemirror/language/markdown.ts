/* Copyright 2023 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { parseMixed } from "@lezer/common";
import { python, pythonLanguage } from "@codemirror/lang-python";
import dedent from "dedent";
import { logNever } from "@/utils/assertNever";

const prefixKinds = ["", "f", "r", "fr", "rf"] as const;
type PrefixKind = (typeof prefixKinds)[number];

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ['"', '"'],
  ["'", "'"],
];
// explode into all combinations
const pairs = prefixKinds.flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end])
);

const regexes = pairs.map(
  ([start, end]) =>
    // mo.md( + any number of spaces + start + capture + any number of spaces + end)
    [
      start,
      new RegExp(`^mo\\.md\\(\\s*${start}(.*)${end}\\s*\\)$`, "s"),
    ] as const
);

/**
 * Language adapter for Markdown.
 */
export class MarkdownLanguageAdapter implements LanguageAdapter {
  type = "markdown" as const;

  lastQuotePrefix: PrefixKind = "";

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1].trim();

        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        // store the quote prefix for later when we transform out
        this.lastQuotePrefix = quotePrefix;
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        return [dedent(unescapedCode), offset];
      }
    }

    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    // Get the quote type from the last transformIn
    // const prefix = upgradePrefixKind(this.lastQuotePrefix, code);
    const prefix = this.lastQuotePrefix;

    const isOneLine = !code.includes("\n");
    if (isOneLine) {
      const escapedCode = code.replaceAll('"', '\\"');
      const start = `mo.md(${prefix}"`;
      const end = `")`;
      return [start + escapedCode + end, start.length];
    }

    // Multiline code
    const start = `mo.md(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', '\\"""');
    const end = `\n    """\n)`;
    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    const markdownLines = pythonCode
      .split("\n")
      .map((line) => line.startsWith("mo.md("))
      .filter(Boolean);
    if (markdownLines.length > 1) {
      // more than line starting with mo.md(; as a heuristic,
      // don't show "view as markdown"
      return false;
    }
    return regexes.some(([, regex]) => regex.test(pythonCode));
  }

  getExtension(): Extension {
    return [
      markdown({
        codeLanguages: languages,
        extensions: [
          // Wrapper extension to handle f-string substitutions
          {
            wrap: parseMixed((node, input) => {
              const text = input.read(node.from, node.to);
              const overlays: Array<{ from: number; to: number }> = [];

              // Find all { } groupings
              const pattern = /{(.*?)}/g;
              let match;

              while ((match = pattern.exec(text)) !== null) {
                const start = match.index + 1;
                const end = pattern.lastIndex - 1;
                overlays.push({ from: start, to: end });
              }

              if (overlays.length === 0) {
                return null;
              }

              return {
                parser: pythonLanguage.parser,
                overlays,
              };
            }),
          },
        ],
      }),
      python().support,
    ];
  }
}

// Remove the f, r, fr, rf prefixes from the quote
function splitQuotePrefix(quote: string): [PrefixKind, string] {
  // start with the longest prefix
  const prefixKindsByLength = [...prefixKinds].sort(
    (a, b) => b.length - a.length
  );
  for (const prefix of prefixKindsByLength) {
    if (quote.startsWith(prefix)) {
      return [prefix, quote.slice(prefix.length)];
    }
  }
  return ["", quote];
}

export function upgradePrefixKind(kind: PrefixKind, code: string): PrefixKind {
  const containsSubstitution = code.includes("{") && code.includes("}");

  // If there is no substitution, keep the same prefix
  if (!containsSubstitution) {
    return kind;
  }

  // If there is a substitution, upgrade to an f-string
  switch (kind) {
    case "":
      return "f";
    case "r":
      return "rf";
    case "f":
    case "rf":
    case "fr":
      return kind;
    default:
      logNever(kind);
      return "f";
  }
}

// Indent each line by one tab
function indentOneTab(code: string): string {
  return code
    .split("\n")
    .map((line) => (line.trim() === "" ? line : `    ${line}`))
    .join("\n");
}
