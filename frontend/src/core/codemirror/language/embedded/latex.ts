/* Copyright 2024 Marimo. All rights reserved. */

// This file has been adapted from https://github.com/jupyterlab/jupyterlab/blob/0dbe74708be66cb9ac423c0fb47c66418c037a8f/packages/codemirror/src/extensions/ipython-md.ts
// Copyright (c) 2015-2025 Project Jupyter Contributors
// All rights reserved.

// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:

// 1. Redistributions of source code must retain the above copyright notice, this
//    list of conditions and the following disclaimer.

// 2. Redistributions in binary form must reproduce the above copyright notice,
//    this list of conditions and the following disclaimer in the documentation
//    and/or other materials provided with the distribution.

// 3. Neither the name of the copyright holder nor the names of its
//    contributors may be used to endorse or promote products derived from
//    this software without specific prior written permission.

// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import { parseMixed, type Parser } from "@lezer/common";
import { tags } from "@lezer/highlight";
import type {
  DelimiterType,
  InlineContext,
  MarkdownConfig,
  NodeSpec,
} from "@lezer/markdown";

// Mathematical expression delimiters
const INLINE_MATH_DOLLAR = "InlineMathDollar";
const INLINE_MATH_BRACKET = "InlineMathBracket";
const BLOCK_MATH_DOLLAR = "BlockMathDollar";
const BLOCK_MATH_BRACKET = "BlockMathBracket";

/**
 * Length of the delimiter for a math expression
 */
const DELIMITER_LENGTH: Record<string, number> = {
  [INLINE_MATH_DOLLAR]: 1,
  [INLINE_MATH_BRACKET]: 3,
  [BLOCK_MATH_DOLLAR]: 2,
  [BLOCK_MATH_BRACKET]: 3,
};

const CHARS_CODES = {
  DOLLAR: 36, // $
  BACKSLASH: 92, // \
  OPEN_PAREN: 40, // (
  CLOSE_PAREN: 41, // )
  OPEN_BRACKET: 91, // [
  CLOSE_BRACKET: 93, // ]
};

/**
 * Delimiters for math expressions
 */
// Delimiters must be defined as constant because they are used in object match tests
const DELIMITERS = Object.keys(DELIMITER_LENGTH).reduce<
  Record<string, DelimiterType>
>((agg, name) => {
  agg[name] = { mark: `${name}Mark`, resolve: name };
  return agg;
}, {});

/**
 * Define a LaTeX mathematical expression parser for Markdown.
 *
 * @param latexParser CodeMirror {@link Parser} for LaTeX mathematical expression
 * @returns Markdown extension
 */
export function parseLatex(latexParser: Parser): MarkdownConfig {
  const defineNodes = new Array<NodeSpec>();
  Object.keys(DELIMITER_LENGTH).forEach((name) => {
    defineNodes.push(
      {
        name,
        style: tags.emphasis,
      },
      { name: `${name}Mark`, style: tags.processingInstruction },
    );
  });
  return {
    defineNodes,
    parseInline: [
      {
        name: BLOCK_MATH_DOLLAR,
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.DOLLAR ||
            cx.char(pos + 1) !== CHARS_CODES.DOLLAR
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[BLOCK_MATH_DOLLAR],
            pos,
            pos + DELIMITER_LENGTH[BLOCK_MATH_DOLLAR],
            true,
            true,
          );
        },
      },
      {
        name: INLINE_MATH_DOLLAR,
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.DOLLAR ||
            cx.char(pos + 1) === CHARS_CODES.DOLLAR
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[INLINE_MATH_DOLLAR],
            pos,
            pos + DELIMITER_LENGTH[INLINE_MATH_DOLLAR],
            true,
            true,
          );
        },
      },
      // Inline expression wrapped in \\( ... \\)
      {
        name: INLINE_MATH_BRACKET,
        before: "Escape", // Search for this delimiter before the escape character
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.BACKSLASH ||
            cx.char(pos + 1) !== CHARS_CODES.BACKSLASH ||
            ![CHARS_CODES.OPEN_PAREN, CHARS_CODES.CLOSE_PAREN].includes(
              cx.char(pos + 2),
            )
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[INLINE_MATH_BRACKET],
            pos,
            pos + DELIMITER_LENGTH[INLINE_MATH_BRACKET],
            cx.char(pos + 2) === CHARS_CODES.OPEN_PAREN,
            cx.char(pos + 2) === CHARS_CODES.CLOSE_PAREN,
          );
        },
      },
      // Block expression wrapped in \\[ ... \\]
      {
        name: BLOCK_MATH_BRACKET,
        before: "Escape", // Search for this delimiter before the escape character
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.BACKSLASH ||
            cx.char(pos + 1) !== CHARS_CODES.BACKSLASH ||
            ![CHARS_CODES.OPEN_BRACKET, CHARS_CODES.CLOSE_BRACKET].includes(
              cx.char(pos + 2),
            )
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[BLOCK_MATH_BRACKET],
            pos,
            pos + DELIMITER_LENGTH[BLOCK_MATH_BRACKET],
            cx.char(pos + 2) === CHARS_CODES.OPEN_BRACKET,
            cx.char(pos + 2) === CHARS_CODES.CLOSE_BRACKET,
          );
        },
      },
      // Inline expression wrapped in \( ... \)
      {
        name: INLINE_MATH_BRACKET,
        before: "Escape",
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.BACKSLASH ||
            ![CHARS_CODES.OPEN_PAREN, CHARS_CODES.CLOSE_PAREN].includes(
              cx.char(pos + 1),
            )
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[INLINE_MATH_BRACKET],
            pos,
            pos + 2, // Length of \( or \)
            cx.char(pos + 1) === CHARS_CODES.OPEN_PAREN,
            cx.char(pos + 1) === CHARS_CODES.CLOSE_PAREN,
          );
        },
      },
      // Block expression wrapped in \[ ... \]
      {
        name: BLOCK_MATH_BRACKET,
        before: "Escape",
        parse(cx: InlineContext, next: number, pos: number): number {
          if (
            next !== CHARS_CODES.BACKSLASH ||
            ![CHARS_CODES.OPEN_BRACKET, CHARS_CODES.CLOSE_BRACKET].includes(
              cx.char(pos + 1),
            )
          ) {
            return -1;
          }

          return cx.addDelimiter(
            DELIMITERS[BLOCK_MATH_BRACKET],
            pos,
            pos + 2, // Length of \[ or \]
            cx.char(pos + 1) === CHARS_CODES.OPEN_BRACKET,
            cx.char(pos + 1) === CHARS_CODES.CLOSE_BRACKET,
          );
        },
      },
    ],
    wrap: parseMixed((node) => {
      // Test if the node type is one of the math expression
      const delimiterLength = DELIMITER_LENGTH[node.type.name];
      if (delimiterLength) {
        const from = node.from + delimiterLength;
        const to = node.to - delimiterLength;

        // Ensure valid ranges
        if (from >= to || from < 0 || to < 0) {
          return null;
        }

        return {
          parser: latexParser,
          // Remove delimiter from LaTeX parser otherwise it won't be highlighted
          overlay: [
            {
              from,
              to,
            },
          ],
        };
      }

      return null;
    }),
  };
}
