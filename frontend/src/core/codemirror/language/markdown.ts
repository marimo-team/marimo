/* Copyright 2023 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";
import { LanguageAdapter } from "./types";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { parseMixed } from "@lezer/common";
import { python, pythonLanguage } from "@codemirror/lang-python";

const pairs = [
  ['"""', '"""'],
  ["'''", "'''"],
  ['"', '"'],
  ["'", "'"],
  ['f"""', '"""'],
  ["f'''", "'''"],
  ['f"', '"'],
  ["f'", "'"],
];

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

  transformIn(pythonCode: string): [string, number] {
    if (!this.isSupported(pythonCode)) {
      throw new Error("Not supported");
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];

        const quoteType = start.startsWith("f") ? start.slice(1) : start;
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        return [unescapedCode, offset];
      }
    }

    return [pythonCode, 0];
  }

  transformOut(code: string): [string, number] {
    const start = `mo.md(f"""`;
    const end = `""")`;
    // escaped quotes
    const escapedCode = code.replaceAll('"""', '\\"""');
    return [start + escapedCode + end, start.length];
  }

  isSupported(pythonCode: string): boolean {
    // more than one mo.md() call
    const matches = pythonCode.match(/mo\.md\(/g);
    if (matches && matches.length > 1) {
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
