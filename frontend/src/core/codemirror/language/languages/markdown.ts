/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import type { LanguageAdapter } from "../types";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { languages } from "@codemirror/language-data";
import { stexMath } from "@codemirror/legacy-modes/mode/stex";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";
import { autocompletion } from "@codemirror/autocomplete";
import { enhancedMarkdownExtension } from "../../markdown/extension";
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import {
  QUOTE_PREFIX_KINDS,
  type QuotePrefixKind,
  splitQuotePrefix,
} from "../utils/quotes";
import { markdownAutoRunExtension } from "../../cells/extensions";
import type { PlaceholderType } from "../../config/types";
import type { CellId } from "@/core/cells/ids";
import { parseLatex } from "../embedded/latex";
import { StreamLanguage } from "@codemirror/language";
import { parsePython } from "../embedded/embedded-python";
import { conditionalCompletion } from "../../completion/utils";
import { pythonCompletionSource } from "../../completion/completer";
import { markdownCompletionSources } from "../../markdown/completions";
import { type EditorView, ViewPlugin } from "@codemirror/view";
import { languageMetadataField } from "../metadata";

export interface MarkdownLanguageAdapterMetadata {
  quotePrefix: QuotePrefixKind;
}

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
export class MarkdownLanguageAdapter
  implements LanguageAdapter<MarkdownLanguageAdapterMetadata>
{
  readonly type = "markdown";
  readonly defaultCode = 'mo.md(r"""\n""")';

  static fromMarkdown(markdown: string) {
    return `mo.md(r"""\n${markdown}\n""")`;
  }

  transformIn(
    pythonCode: string,
  ): [string, number, MarkdownLanguageAdapterMetadata] {
    pythonCode = pythonCode.trim();

    const metadata: MarkdownLanguageAdapterMetadata = {
      quotePrefix: "r",
    };

    // empty string
    if (pythonCode === "") {
      return ["", 0, metadata];
    }

    for (const [start, regex] of regexes) {
      const match = pythonCode.match(regex);
      if (match) {
        const innerCode = match[1];
        const [quotePrefix, quoteType] = splitQuotePrefix(start);
        metadata.quotePrefix = quotePrefix;
        const unescapedCode = innerCode.replaceAll(`\\${quoteType}`, quoteType);

        const offset = pythonCode.indexOf(innerCode);
        // string-dedent expects the first and last line to be empty / contain only whitespace, so we pad with \n
        return [dedent(`\n${unescapedCode}\n`).trim(), offset, metadata];
      }
    }

    // no match
    return [pythonCode, 0, metadata];
  }

  transformOut(
    code: string,
    metadata: MarkdownLanguageAdapterMetadata,
  ): [string, number] {
    // Empty string
    if (code === "") {
      // Need at least a space, otherwise the output will be 6 quotes
      code = " ";
    }

    const { quotePrefix } = metadata;

    // We always transform back with triple quotes, as to avoid needing to
    // escape single quotes.
    const escapedCode = code.replaceAll('"""', String.raw`\"""`);

    // If its one line and not bounded by quotes, write it as single line
    const isOneLine = !code.includes("\n");
    const boundedByQuote = code.startsWith('"') || code.endsWith('"');
    if (isOneLine && !boundedByQuote) {
      const start = `mo.md(${quotePrefix}"""`;
      const end = `""")`;
      return [start + escapedCode + end, start.length];
    }

    // Multiline code
    const start = `mo.md(\n    ${quotePrefix}"""\n`;
    const end = `\n"""\n)`;
    return [start + escapedCode + end, start.length + 1];
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

  getExtension(
    _cellId: CellId,
    _completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    _: PlaceholderType,
  ): Extension[] {
    const markdownLanguageData = markdown().language.data;
    let view: EditorView | undefined;

    // Only activate completions for f-strings
    const isFStringActive = () => {
      const metadata = view?.state.field(languageMetadataField);
      if (metadata === undefined) {
        return false;
      }
      return metadata.quotePrefix?.includes("f") ?? false;
    };

    return [
      ViewPlugin.define((_view) => {
        view = _view;
        return {};
      }),
      markdown({
        base: markdownLanguage,
        codeLanguages: languages,
        extensions: [
          // Embedded LateX in Markdown
          parseLatex(StreamLanguage.define(stexMath).parser),
          // Embedded Python in Markdown
          parsePython(pythonLanguage.parser, isFStringActive),
        ],
      }),
      enhancedMarkdownExtension(hotkeys),
      // Completions for markdown
      markdownCompletionSources.map((source) =>
        markdownLanguageData.of({ autocomplete: source }),
      ),
      // Completions for embedded Python
      python().language.data.of({
        autocomplete: conditionalCompletion({
          completion: pythonCompletionSource,
          predicate: isFStringActive,
        }),
      }),

      autocompletion({
        // We remove the default keymap because we use our own which
        // handles the Escape key correctly in Vim
        defaultKeymap: false,
        activateOnTyping: true,
      }),
      // Markdown autorun
      markdownAutoRunExtension({ predicate: () => !isFStringActive() }),
    ];
  }
}
