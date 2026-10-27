/* Copyright 2026 Marimo. All rights reserved. */

import type {
  CompletionContext,
  CompletionResult,
} from "@codemirror/autocomplete";
import { python } from "@codemirror/lang-python";
import { type Parser, parseMixed } from "@lezer/common";
import { tags } from "@lezer/highlight";
import type { InlineContext, MarkdownConfig } from "@lezer/markdown";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import { getVariableCompletions } from "../../completion/variable-completions";

// Python code block delimiters
const PYTHON = "Python";

const OPEN_BRACE = 123; // {
const DELIMITER_LENGTH = 1;

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
  const replacements = new WeakMap<
    InlineContext,
    { ends: Map<number, number>; parsedTo: number }
  >();

  const defineNodes = [
    { name: PYTHON, style: tags.emphasis },
    { name: `${PYTHON}Mark`, style: tags.processingInstruction },
  ];

  return {
    defineNodes,
    parseInline: [
      {
        name: PYTHON,
        before: "Escape",
        parse(cx: InlineContext, next: number, pos: number): number {
          if (!isActivated()) {
            return -1;
          }

          // A backslash does not escape a brace in Python f-strings.
          if (next === 92 && cx.char(pos + 1) === OPEN_BRACE) {
            return pos + 1;
          }
          if (next !== OPEN_BRACE) {
            return -1;
          }
          if (cx.char(pos + 1) === OPEN_BRACE) {
            return pos + 2;
          }

          let cached = replacements.get(cx);
          if (!cached || pos >= cached.parsedTo) {
            // Cache all replacements so each brace does not reparse the paragraph.
            // Keep Markdown backslashes from consuming braces as Python escapes.
            const prefix = 'rf"""';
            const tree = pythonParser.parse(
              `${prefix}${cx.slice(pos, cx.end)}\n"""`,
            );
            const formatString = tree.topNode
              .getChild("ExpressionStatement")
              ?.getChild("FormatString");
            const offset = pos - prefix.length;
            const ends = new Map<number, number>();
            for (const replacement of formatString?.getChildren(
              "FormatReplacement",
            ) ?? []) {
              if (replacement.lastChild?.name === "}") {
                ends.set(offset + replacement.from, offset + replacement.to);
              }
            }
            cached = {
              ends,
              parsedTo: formatString ? offset + formatString.to : cx.end,
            };
            replacements.set(cx, cached);
          }
          const end = cached.ends.get(pos);
          if (end === undefined) {
            return -1;
          }
          return cx.addElement(
            cx.elt(PYTHON, pos, end, [
              cx.elt(`${PYTHON}Mark`, pos, pos + 1),
              cx.elt(`${PYTHON}Mark`, end - 1, end),
            ]),
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

  // Check it is not double {{
  if (beforeCursor.at(lastOpenBrace - 1) === "{") {
    return null;
  }

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
