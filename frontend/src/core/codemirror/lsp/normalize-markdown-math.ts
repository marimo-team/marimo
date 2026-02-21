/* Copyright 2026 Marimo. All rights reserved. */

import type * as LSP from "vscode-languageserver-protocol";

// Matches inline RST math role: :math:`...`
const INLINE_MATH_ROLE_REGEX = /(?<!`):math:`([^\n`]+)`/g;
// Matches role variant with HTML code tag: :math:<code>...</code>
const INLINE_MATH_ROLE_CODE_REGEX = /:math:\s*<code>(.+?)<\/code>/gs;
// Matches display bracket delimiters: \[...\]
const DISPLAY_BRACKET_REGEX = /\\\[(.+?)\\]/gs;
// Matches inline paren delimiters: \(...\)
const INLINE_PAREN_REGEX = /\\\((.+?)\\\)/gs;
// Matches display dollar delimiters: $$...$$
const DISPLAY_DOLLAR_REGEX = /(?<!\\)\$\$(.+?)(?<!\\)\$\$/gs;
// Matches inline dollar delimiters: $...$
const INLINE_DOLLAR_REGEX = /(?<![$\\])\$(?!\$)([^\n$]+?)(?<!\\)\$(?!\$)/g;

interface FencedSegment {
  text: string;
  isFenced: boolean;
}

interface InlineCodeSegment {
  text: string;
  isInlineCode: boolean;
}

/**
 * Normalize supported math syntaxes inside markdown payloads used by LSP.
 *
 * The output stays markdown/HTML-compatible for the tooltip renderer while
 * skipping fenced and inline code so examples remain literal.
 */
export function normalizeMarkdownMath(markdown: string): string {
  if (!containsMathSyntax(markdown)) {
    return markdown;
  }

  return splitByFencedCodeBlocks(markdown)
    .map((segment) => {
      if (segment.isFenced) {
        return segment.text;
      }

      const withMathRolesNormalized = segment.text
        .replaceAll(INLINE_MATH_ROLE_REGEX, (_, math) => inlineMath(math))
        .replaceAll(INLINE_MATH_ROLE_CODE_REGEX, (_, math) => inlineMath(math));

      return splitByInlineCodeSegments(withMathRolesNormalized)
        .map((inlineSegment) => {
          if (inlineSegment.isInlineCode) {
            return inlineSegment.text;
          }
          return normalizePlainTextMath(inlineSegment.text);
        })
        .join("");
    })
    .join("");
}

/**
 * Apply markdown math normalization across the LSP documentation union.
 *
 * For plaintext payloads, this only upcasts to markdown when math syntax is
 * detected, so non-math plaintext keeps its previous behavior.
 */
export function normalizeLspDocumentation(
  documentation:
    | LSP.MarkupContent
    | LSP.MarkedString
    | LSP.MarkedString[]
    | undefined,
): LSP.MarkupContent | LSP.MarkedString | LSP.MarkedString[] | undefined {
  if (documentation == null) {
    return documentation;
  }

  if (Array.isArray(documentation)) {
    return documentation.map((item) => normalizeLspMarkedString(item));
  }

  if (typeof documentation === "string") {
    return normalizeMarkdownMath(documentation);
  }

  if (isMarkupContent(documentation)) {
    if (documentation.kind === "markdown") {
      return {
        ...documentation,
        value: normalizeMarkdownMath(documentation.value),
      };
    }

    if (!containsMathSyntax(documentation.value)) {
      return documentation;
    }

    return {
      kind: "markdown",
      value: normalizeMarkdownMath(documentation.value),
    };
  }

  return normalizeLspMarkedString(documentation);
}

function normalizeLspMarkedString(marked: LSP.MarkedString): LSP.MarkedString {
  if (typeof marked === "string") {
    return normalizeMarkdownMath(marked);
  }
  if (marked.language !== "markdown" && marked.language !== "md") {
    return marked;
  }
  return {
    ...marked,
    value: normalizeMarkdownMath(marked.value),
  };
}

function isMarkupContent(
  documentation: LSP.MarkupContent | LSP.MarkedString,
): documentation is LSP.MarkupContent {
  return (
    typeof documentation === "object" &&
    "kind" in documentation &&
    "value" in documentation
  );
}

function containsMathSyntax(markdown: string): boolean {
  return (
    markdown.includes(".. math::") ||
    markdown.includes(":math:`") ||
    // Detects display bracket delimiters.
    /\\\[[\S\s]+?\\]/.test(markdown) ||
    // Detects inline paren delimiters.
    /\\\([\S\s]+?\\\)/.test(markdown) ||
    // Detects display dollar delimiters.
    /(?<!\\)\$\$[\S\s]+?(?<!\\)\$\$/.test(markdown) ||
    // Detects inline dollar delimiters.
    /(?<![$\\])\$(?!\$)[^\n$]+?(?<!\\)\$(?!\$)/.test(markdown) ||
    // Detects HTML code-tag RST role variant.
    /:math:\s*<code>[\S\s]+?<\/code>/.test(markdown)
  );
}

function splitByFencedCodeBlocks(markdown: string): FencedSegment[] {
  // Preserve fenced code blocks as literal text during normalization.
  const lines = markdown.split("\n");
  const segments: FencedSegment[] = [];
  let current: string[] = [];
  let inFence = false;
  let fenceChar = "";
  let fenceLength = 0;

  const flush = (isFenced: boolean) => {
    if (current.length === 0) {
      return;
    }
    segments.push({ text: current.join("\n"), isFenced });
    current = [];
  };

  for (const line of lines) {
    // Matches fenced-code fence markers: ``` or ~~~ (>= 3 chars).
    const markerMatch = line.match(/^[\t ]*(`{3,}|~{3,})/);
    if (markerMatch) {
      const marker = markerMatch[1];
      const markerChar = marker[0];
      const markerLength = marker.length;

      if (!inFence) {
        flush(false);
        inFence = true;
        fenceChar = markerChar;
        fenceLength = markerLength;
        current.push(line);
        continue;
      }

      if (markerChar === fenceChar && markerLength >= fenceLength) {
        current.push(line);
        flush(true);
        inFence = false;
        fenceChar = "";
        fenceLength = 0;
        continue;
      }
    }

    current.push(line);
  }

  flush(inFence);
  return segments;
}

function splitByInlineCodeSegments(text: string): InlineCodeSegment[] {
  // Preserve inline code spans (single or multi-backtick delimiters).
  const segments: InlineCodeSegment[] = [];
  let current = "";
  let inInlineCode = false;
  let delimiter = "";
  let i = 0;

  while (i < text.length) {
    if (text[i] === "`") {
      let j = i;
      while (j < text.length && text[j] === "`") {
        j += 1;
      }
      const ticks = text.slice(i, j);

      if (inInlineCode && ticks === delimiter) {
        current += ticks;
        segments.push({ text: current, isInlineCode: true });
        current = "";
        inInlineCode = false;
        delimiter = "";
        i = j;
        continue;
      }

      if (!inInlineCode) {
        if (current) {
          segments.push({ text: current, isInlineCode: false });
          current = "";
        }
        inInlineCode = true;
        delimiter = ticks;
        current += ticks;
        i = j;
        continue;
      }
    }

    current += text[i];
    i += 1;
  }

  if (current) {
    segments.push({ text: current, isInlineCode: inInlineCode });
  }

  return segments;
}

function normalizePlainTextMath(text: string): string {
  // Convert alternate math syntaxes into marimo-tex HTML wrappers.
  let converted = convertRstMathBlocks(text);
  converted = converted.replaceAll(DISPLAY_BRACKET_REGEX, (_, math) =>
    displayMath(math),
  );
  converted = converted.replaceAll(INLINE_PAREN_REGEX, (_, math) =>
    inlineMath(math),
  );
  converted = converted.replaceAll(DISPLAY_DOLLAR_REGEX, (_, math) =>
    displayMath(math),
  );
  converted = converted.replaceAll(INLINE_DOLLAR_REGEX, (_, math) =>
    inlineMath(math),
  );
  return converted;
}

function countIndent(line: string): number {
  // Matches leading whitespace used to compute visual indentation.
  return line.match(/^[\t ]*/)?.[0].replaceAll("\t", "    ").length ?? 0;
}

function convertRstMathBlocks(text: string): string {
  // Convert ``.. math::`` directive bodies to display math wrappers.
  const lines = text.split("\n");
  if (lines.length === 0) {
    return text;
  }

  const output: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Matches RST math directive lines: ".. math:: ..."
    const directiveMatch = line.match(/^[\t ]*\.\.\s+math::(.*)$/);
    if (!directiveMatch) {
      output.push(line);
      i += 1;
      continue;
    }

    const inlineMath = directiveMatch[1]?.trim() ?? "";
    const baseIndent = countIndent(line);
    i += 1;

    const mathLines: string[] = [];
    let consumeUnindentedBlock = inlineMath.includes("\\begin");
    if (inlineMath) {
      mathLines.push(inlineMath);
    } else {
      while (i < lines.length) {
        const currentLine = lines[i];
        if (!currentLine.trim()) {
          i += 1;
          continue;
        }

        const isOptionLine =
          countIndent(currentLine) > baseIndent &&
          currentLine.trim().startsWith(":");
        if (!isOptionLine) {
          break;
        }
        i += 1;
      }

      if (i < lines.length) {
        const nextLine = lines[i];
        consumeUnindentedBlock =
          Boolean(nextLine.trim()) &&
          countIndent(nextLine) <= baseIndent &&
          nextLine.trimStart().startsWith("\\");
      }
    }

    if (consumeUnindentedBlock) {
      while (i < lines.length && lines[i].trim()) {
        mathLines.push(lines[i]);
        i += 1;
      }
    } else {
      while (i < lines.length) {
        const currentLine = lines[i];
        if (!currentLine.trim()) {
          mathLines.push("");
          i += 1;
          continue;
        }

        if (countIndent(currentLine) <= baseIndent) {
          break;
        }

        mathLines.push(currentLine);
        i += 1;
      }
    }

    const nonEmptyMathLines = mathLines.filter((mathLine) =>
      Boolean(mathLine.trim()),
    );
    if (nonEmptyMathLines.length === 0) {
      output.push(line);
      continue;
    }

    const minIndent = Math.min(
      ...nonEmptyMathLines.map((mathLine) => countIndent(mathLine)),
    );
    const normalizedMath = mathLines
      .map((mathLine) => {
        if (!mathLine) {
          return "";
        }
        const stripCount = Math.min(minIndent, countIndent(mathLine));
        return mathLine.slice(stripCount);
      })
      .join("\n")
      .trim();

    output.push(displayMath(normalizedMath));
  }

  return output.join("\n");
}

function inlineMath(math: string): string {
  return `<marimo-tex class="arithmatex">||(${math.trim()}||)</marimo-tex>`;
}

function displayMath(math: string): string {
  return `<marimo-tex class="arithmatex">||[${math.trim()}||]</marimo-tex>`;
}
