/* Copyright 2026 Marimo. All rights reserved. */

import { pythonLanguage } from "@codemirror/lang-python";
import dedent from "string-dedent";
import type {
  FormatResult,
  LanguageParser,
  ParseResult,
  QuotePrefixKind,
} from "../types.js";
import { QUOTE_PREFIX_KINDS } from "../types.js";
import { splitQuotePrefix, unescapeQuotes } from "../utils/index.js";

export interface MarkdownMetadata {
  quotePrefix: QuotePrefixKind;
}

const quoteKinds = [
  ['"""', '"""'],
  ["'''", "'''"],
  ['"', '"'],
  ["'", "'"],
] as const;

// Explode into all combinations of prefixes and quote types
const pairs = QUOTE_PREFIX_KINDS.flatMap((prefix) =>
  quoteKinds.map(([start, end]) => [prefix + start, end] as const),
);

const regexes = pairs.map(
  ([start, end]) =>
    [
      start,
      new RegExp(
        `^mo\\.md\\(\\s*${escapeRegex(start)}(.*)${escapeRegex(end)}\\s*\\)$`,
        "s",
      ),
    ] as const,
);

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Escape each triple quote as `\"""`, which `unescapeQuotes` reverses.
 * Runs are escaped from their end, so at most two unescaped quotes touch.
 * Returns undefined when a run of 3k quotes follows an odd number of
 * backslashes: the added backslash would pair with the last of them.
 */
function escapeTripleQuotes(
  code: string,
  quote: '"' | "'",
): string | undefined {
  const runs = String.raw`(?:${quote}{3})+(?!${quote})`;
  if (new RegExp(String.raw`(?<!\\)(?:\\\\)*\\${runs}`).test(code)) {
    return undefined;
  }
  const triple = quote.repeat(3);
  return code.replace(new RegExp(runs, "g"), (run) =>
    run.replaceAll(triple, `\\${triple}`),
  );
}

/**
 * Parser for marimo Markdown cells (mo.md()).
 *
 * Converts between Python code like `mo.md(r"""# Hello""")` and
 * plain Markdown like `# Hello`.
 */
export class MarkdownParser implements LanguageParser<MarkdownMetadata> {
  readonly type = "markdown";
  readonly defaultCode = 'mo.md(r"""\n""")';
  readonly defaultMetadata: MarkdownMetadata = {
    quotePrefix: "r",
  };

  /**
   * Create a markdown cell from markdown content.
   */
  static fromMarkdown(markdown: string): string {
    return `mo.md(r"""\n${markdown}\n""")`;
  }

  transformIn(pythonCode: string): ParseResult<MarkdownMetadata> {
    pythonCode = pythonCode.trim();

    const metadata: MarkdownMetadata = { ...this.defaultMetadata };

    // Empty string
    if (pythonCode === "") {
      return { code: "", offset: 0, metadata };
    }

    // Try to match against all known patterns
    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];
        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        metadata.quotePrefix = quotePrefix;
        const unescapedCode = unescapeQuotes(innerCode, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        // string-dedent expects the first and last line to be empty / contain only whitespace,
        // so we pad with \n
        return {
          code: dedent(`\n${unescapedCode}\n`).trim(),
          offset,
          metadata,
        };
      }
    }

    // No match - return original code
    return { code: pythonCode, offset: 0, metadata };
  }

  transformOut(code: string, metadata: MarkdownMetadata): FormatResult {
    // NB. Must be kept consistent with
    // marimo/_convert/common/format.py::markdown_to_marimo for raw prefixes.
    // Non-raw prefixes are not handled here because transformIn does not
    // evaluate escape sequences, so the editor could not read them back.

    // Empty string
    if (code === "") {
      // Need at least a space, otherwise the output will be 6 quotes
      code = " ";
    }

    const { quotePrefix } = metadata;

    // Prefer a delimiter the body does not contain: escapes survive in raw
    // strings and render as backslashes in code blocks.
    const quotes: Array<'"' | "'"> =
      code.includes('"""') && !code.includes("'''") ? ["'"] : ['"', "'"];
    for (const quote of quotes) {
      const escapedCode = escapeTripleQuotes(code, quote);
      if (escapedCode !== undefined) {
        const start = `mo.md(${quotePrefix}${quote.repeat(3)}\n`;
        const end = `\n${quote.repeat(3)})`;
        return { code: start + escapedCode + end, offset: start.length + 1 };
      }
    }

    // Neither delimiter can hold this body losslessly. Escape every second
    // quote, which is always valid Python but loads back with backslashes.
    const start = `mo.md(${quotePrefix}"""\n`;
    const end = `\n""")`;
    const escapedCode = code.replaceAll('""', String.raw`"\"`);
    return { code: start + escapedCode + end, offset: start.length + 1 };
  }

  isSupported(pythonCode: string): boolean {
    pythonCode = pythonCode.trim();

    // Empty strings are supported
    if (pythonCode === "") {
      return true;
    }

    // Must start with mo.md(
    if (!pythonCode.startsWith("mo.md(")) {
      return false;
    }

    // Empty function calls are supported
    if (pythonCode === "mo.md()") {
      return true;
    }

    // Parse the code using Lezer and check for the exact match of mo.md() signature
    const tree = pythonLanguage.parser.parse(pythonCode);

    // This is the exact match of mo.md() signature
    const enterOrder: Array<{ match: string | RegExp; stop?: boolean }> = [
      { match: "Script" },
      { match: "ExpressionStatement" },
      { match: "CallExpression" },
      { match: "MemberExpression" },
      { match: "VariableName" },
      { match: "." },
      { match: "PropertyName" },
      { match: "ArgList" },
      { match: "(" },
      { match: /String|FormatString/, stop: true },
      { match: ")" },
    ];

    let isValid = true;

    // Parse the code using Lezer to check for multiple function calls and string content
    tree.iterate({
      enter: (node) => {
        const current = enterOrder.shift();
        if (current === undefined) {
          // If our list is empty, but we are still going
          // then this is not a valid call
          isValid = false;
          return false;
        }

        const match = current.match;

        if (typeof match === "string") {
          isValid = isValid && match === node.name;
          return isValid && !current.stop;
        }

        if (!match.test(node.name)) {
          isValid = false;
          return isValid && !current.stop;
        }

        return isValid && !current.stop;
      },
    });

    return isValid;
  }
}
