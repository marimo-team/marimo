/* Copyright 2026 Marimo. All rights reserved. */
import "./code-placeholder.css";
import { markdownLanguage } from "@codemirror/lang-markdown";
import { pythonLanguage } from "@codemirror/lang-python";
import { SQLDialect } from "@codemirror/lang-sql";
import { classHighlighter, highlightTree } from "@lezer/highlight";
import { type CSSProperties, type ReactNode, useMemo } from "react";
import { parseCellCode } from "@/core/codemirror/language/cell-code";
import { cn } from "@/utils/cn";

interface CodePlaceholderProps {
  code: string;
  className?: string;
}

const parsers = {
  python: pythonLanguage.parser,
  markdown: markdownLanguage.parser,
  sql: SQLDialect.define({}).language.parser,
};

// Rendering every line of every offscreen cell is unbounded work. The rest of a
// long cell is a spacer, so the layout still matches the editor.
const MAX_RENDERED_LINES = 200;

function splitAtLine(text: string, maxLines: number) {
  let end = 0;
  let lines = 0;
  while (lines < maxLines) {
    const newline = text.indexOf("\n", end);
    if (newline === -1) {
      return { shown: text, hiddenLines: 0 };
    }
    end = newline + 1;
    lines++;
  }
  const hidden = text.slice(end - 1);
  return {
    shown: text.slice(0, end - 1),
    hiddenLines: hidden.split("\n").length - 1,
  };
}

export const CodePlaceholder = ({ code, className }: CodePlaceholderProps) => {
  const { content, gutterDigits, hiddenLines } = useMemo(() => {
    const { adapter, text: fullText } = parseCellCode(code);
    const { shown: text, hiddenLines } = splitAtLine(
      fullText,
      MAX_RENDERED_LINES,
    );
    const parser = parsers[adapter.type];
    const nodes: ReactNode[] = [];
    let position = 0;
    highlightTree(parser.parse(text), classHighlighter, (from, to, classes) => {
      if (from > position) {
        nodes.push(text.slice(position, from));
      }
      nodes.push(
        <span key={from} className={classes}>
          {text.slice(from, to)}
        </span>,
      );
      position = to;
    });
    nodes.push(text.slice(position));
    // A final newline needs a following character to occupy its own line.
    if (!text || text.endsWith("\n")) {
      nodes.push("\u200b");
    }
    return {
      content: nodes,
      gutterDigits: String(fullText.split("\n").length).length,
      hiddenLines,
    };
  }, [code]);
  return (
    <div
      className={cn("cm", "mo-code-placeholder", className)}
      data-testid="cell-editor-placeholder"
      style={
        {
          "--mo-gutter-digits": gutterDigits,
          "--mo-hidden-lines": hiddenLines,
        } as CSSProperties
      }
    >
      {content}
      {hiddenLines > 0 && <div className="mo-code-placeholder-rest" />}
    </div>
  );
};
