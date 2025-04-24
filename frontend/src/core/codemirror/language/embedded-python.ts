/* Copyright 2024 Marimo. All rights reserved. */

import { parseMixed, type Parser } from "@lezer/common";
import { tags } from "@lezer/highlight";
import type { InlineContext, MarkdownConfig } from "@lezer/markdown";
import { python } from "@codemirror/lang-python";

import { store } from "@/core/state/jotai";
import type {
  CompletionContext,
  CompletionResult,
} from "@codemirror/autocomplete";
import { variablesAtom } from "@/core/variables/state";
import type { Extension } from "@codemirror/state";
import { getVariableCompletions } from "../completion/variable-completions";

// Python code block delimiters
const PYTHON = "Python";

const OPEN_BRACE = 123; // {
const CLOSE_BRACE = 125; // }
const DELIMITER_LENGTH = 1;

const MARK = { mark: `${PYTHON}Mark`, resolve: PYTHON };

/**
 * Define a Python code block parser for Markdown.
 *
 * @param pythonParser CodeMirror {@link Parser} for Python code
 * @returns Markdown extension
 */
export function parsePython(
  pythonParser: Parser,
  isActivated: () => boolean,
): MarkdownConfig {
  const defineNodes = [
    { name: PYTHON, style: tags.emphasis },
    { name: `${PYTHON}Mark`, style: tags.processingInstruction },
  ];

  return {
    defineNodes,
    parseInline: [
      {
        name: PYTHON,
        parse(cx: InlineContext, next: number, pos: number): number {
          if (!isActivated()) {
            return -1;
          }

          if (next !== OPEN_BRACE && next !== CLOSE_BRACE) {
            return -1;
          }

          return cx.addDelimiter(
            MARK,
            pos,
            pos + DELIMITER_LENGTH,
            next === OPEN_BRACE,
            next === CLOSE_BRACE,
          );
        },
      },
    ],
    wrap: parseMixed((node) => {
      if (!isActivated()) {
        return null;
      }

      if (node.type.name !== PYTHON) {
        return null;
      }

      const from = node.from + DELIMITER_LENGTH;
      const to = node.to - DELIMITER_LENGTH;

      if (from >= to || from < 0 || to < 0) {
        return null;
      }

      return {
        parser: pythonParser,
        overlay: [{ from, to }],
        extensions: [python().support],
      };
    }),
  };
}

const languageData = python().language.data;

/**
 * Embedded Python completions
 *
 * @param isActivated Function that returns whether the extension should be activated
 */
export function embeddedPythonCompletions(
  isActivated: () => boolean,
): Extension {
  return [
    languageData.of({
      autocomplete: (context: CompletionContext): CompletionResult | null => {
        if (!isActivated()) {
          return null;
        }

        // Check if the cursor is at a position where a variable can be inserted
        const wordMatch = context.matchBefore(/\w*$/);
        if (!context.explicit && !wordMatch) {
          return null;
        }

        const filter = wordMatch?.text ?? "";

        const options = getVariableCompletions(
          store.get(variablesAtom),
          new Set(),
        );

        return {
          from: context.pos - filter.length,
          options,
          validFor: /^\w*$/,
        };
      },
    }),
  ];
}

/**
 * Cheap variable completion source without having to go through the
 * backend.
 */
export const variableCompletionSource = (
  context: CompletionContext,
): CompletionResult | null => {
  // Check if we're inside a {} block by looking for an opening brace
  const beforeCursor = context.state.doc.sliceString(0, context.pos);
  const lastOpenBrace = beforeCursor.lastIndexOf("{");

  // If no opening brace or a closing brace appears after the last opening brace, we're not in a {} block
  if (
    lastOpenBrace === -1 ||
    beforeCursor.indexOf("}", lastOpenBrace) > lastOpenBrace
  ) {
    return null;
  }

  // Match the word being typed
  const wordMatch = context.matchBefore(/\w*$/);
  if (!wordMatch) {
    return null;
  }

  const variables = store.get(variablesAtom);
  const options = getVariableCompletions(variables, new Set(), 99);

  return {
    from: wordMatch.from,
    options,
    validFor: /^\w*$/,
  };
};
