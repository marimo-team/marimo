/* Copyright 2024 Marimo. All rights reserved. */

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
    // NB. Must be kept consistent with marimo/_convert/utils.py::markdown_to_marimo

    // Empty string
    if (code === "") {
      // Need at least a space, otherwise the output will be 6 quotes
      code = " ";
    }

    const { quotePrefix } = metadata;

    // We always transform back with triple quotes, as to avoid needing to
    // escape single quotes.
    // We escape only 2 because 4 quotes in a row would end the string.
    const escapedCode = code.replaceAll('""', String.raw`\""`);

    const start = `mo.md(${quotePrefix}"""\n`;
    const end = `\n""")`;
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
