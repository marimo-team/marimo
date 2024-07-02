/* Copyright 2024 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { parseMixed } from "@lezer/common";
import { python, pythonLanguage } from "@codemirror/lang-python";
import dedent from "string-dedent";
import {
  Completion,
  CompletionSource,
  autocompletion,
} from "@codemirror/autocomplete";
import { once } from "lodash-es";
import { enhancedMarkdownExtension } from "../markdown/extension";
import { CompletionConfig } from "@/core/config/config-schema";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { indentOneTab } from "./utils/indentOneTab";
import {
  QuotePrefixKind,
  QUOTE_PREFIX_KINDS,
  splitQuotePrefix,
} from "./utils/quotes";

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ['"', '"'],
  ["'", "'"],
];
// explode into all combinations
const pairs = QUOTE_PREFIX_KINDS.flatMap((prefix) =>
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

/**
 * Language adapter for Markdown.
 */
export class MarkdownLanguageAdapter implements LanguageAdapter {
  readonly type = "markdown";
  readonly defaultCode = 'mo.md(rf"""\n""")';

  lastQuotePrefix: QuotePrefixKind = "";

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
    }

    pythonCode = pythonCode.trim();

    // empty string
    if (pythonCode === "") {
      this.lastQuotePrefix = "rf";
      return ["", 0];
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
    const prefix = this.lastQuotePrefix;

    const isOneLine = !code.includes("\n");
    if (isOneLine) {
      const escapedCode = code.replaceAll('"', String.raw`\"`);
      const start = `mo.md(${prefix}"`;
      const end = `")`;
      return [start + escapedCode + end, start.length];
    }

    // Multiline code
    const start = `mo.md(\n    ${prefix}"""\n`;
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);
    const end = `\n    """\n)`;
    return [start + indentOneTab(escapedCode) + end, start.length + 1];
  }

  isSupported(pythonCode: string): boolean {
    if (pythonCode.trim() === "") {
      return true;
    }

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

  getExtension(
    _completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
  ): Extension[] {
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
      enhancedMarkdownExtension(hotkeys),
      autocompletion({
        activateOnTyping: true,
        override: [emojiCompletionSource],
      }),
      python().support,
    ];
  }
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
  )
    .then((res) => {
      if (!res.ok) {
        throw new Error("Failed to fetch emoji list");
      }
      return res.json() as unknown as Record<string, string[]>;
    })
    .catch(() => {
      // If we can't fetch the emoji list, just return an empty list
      return {};
    });

  return Object.entries(emojiList).map(([emoji, names]) => ({
    shortcode: names[0],
    label: names.map((d) => `:${d}`).join(" "),
    emoji,
    displayLabel: `${emoji} ${names[0].replaceAll("_", " ")}`,
    apply: emoji,
    type: "emoji",
  }));
});
