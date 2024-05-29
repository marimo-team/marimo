/* Copyright 2024 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { parseMixed } from "@lezer/common";
import { python, pythonLanguage } from "@codemirror/lang-python";
import dedent from "string-dedent";
import { logNever } from "@/utils/assertNever";
import {
  Completion,
  CompletionSource,
  autocompletion,
} from "@codemirror/autocomplete";
import { once } from "lodash-es";
import { enhancedMarkdownExtension } from "../markdown/extension";

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
  quoteKinds.map(([start, end]) => [prefix + start, end]),
);

const regexes = pairs.map(
  ([start, end]) =>
    // mo.md( + any number of spaces + start + capture + any number of spaces + end)
    [
      start,
      new RegExp(`^mo\\.md\\(\\s*${start}(.*)${end}\\s*\\)$`, "s"),
    ] as const,
);

type QuoteType = '"' | '"""'; // Define a type that restricts to either single or triple quotes

/**
 * Language adapter for Markdown.
 */
export class MarkdownLanguageAdapter implements LanguageAdapter {
  type = "markdown" as const;

  lastQuotePrefix: PrefixKind = "";
  lastQuoteType: QuoteType = '"'; // Use the new QuoteType here

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];
        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        this.lastQuotePrefix = quotePrefix;
        this.lastQuoteType = quoteType as QuoteType; // Cast to QuoteType
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        return [dedent(`\n${unescapedCode}\n`).trim(), offset];
      }
    }

    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    const prefix = this.lastQuotePrefix;
    const quoteType = this.lastQuoteType; // Already validated as QuoteType

    const isOneLine = !code.includes("\n") && !code.includes('"""');
    if (isOneLine) {
      const escapedCode = code.replaceAll(quoteType, `\\${quoteType}`);
      const start = `mo.md(${prefix}${quoteType}`;
      const end = `${quoteType})`;
      return [start + escapedCode + end, start.length];
    }

    // Multiline code
    const start = `mo.md(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', '\\"""');
    const end = `\n    """)`;
    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "mo.md()") {
      return true;
    }

    const markdownLines = pythonCode
      .trim()
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
      enhancedMarkdownExtension(),
      autocompletion({
        activateOnTyping: true,
        override: [emojiCompletionSource],
      }),
      python().support,
    ];
  }
}

// Remove the f, r, fr, rf prefixes from the quote
function splitQuotePrefix(quote: string): [PrefixKind, string] {
  // start with the longest prefix
  const prefixKindsByLength = [...prefixKinds].sort(
    (a, b) => b.length - a.length,
  );
  for (const prefix of prefixKindsByLength) {
    if (quote.startsWith(prefix)) {
      const remaining = quote.slice(prefix.length);
      if (remaining.startsWith('"""') || remaining.startsWith('"')) {
        return [prefix, remaining];
      }
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

const emojiCompletionSource: CompletionSource = async (context) => {
  // Check if the cursor is at a position where an emoji can be inserted
  if (!context.explicit && !context.matchBefore(/:\w*$/)) {
    return null;
  }

  const emojiList = await getEmojiList();
  const filter = context.matchBefore(/:\w*$/)?.text.slice(1) ?? "";

  return {
    from: context.pos - filter.length - 1,
    options: emojiList,
    validFor: /^[\w:]*$/,
  };
};

// This loads emojis from a CDN
// This only happens for searching for emojis, so when you are not connected to the internet,
// everything works fine, except for autocompletion of emojis
const getEmojiList = once(async (): Promise<Completion[]> => {
  const emojiList = await fetch(
    "https://unpkg.com/emojilib@3.0.11/dist/emoji-en-US.json",
  ).then((res) => res.json() as unknown as Record<string, string[]>);

  return Object.entries(emojiList).map(([emoji, names]) => ({
    shortcode: names[0],
    label: names.map((d) => `:${d}`).join(" "),
    emoji,
    displayLabel: `${emoji} ${names[0].replaceAll("_", " ")}`,
    apply: emoji,
    type: "emoji",
  }));
});
