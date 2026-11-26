/* Copyright 2026 Marimo. All rights reserved. */
import "./code-placeholder.css";
import { markdownLanguage } from "@codemirror/lang-markdown";
import { pythonLanguage } from "@codemirror/lang-python";
import { SQLDialect } from "@codemirror/lang-sql";
import { classHighlighter, highlightTree } from "@lezer/highlight";
import { useMemo, type ReactNode } from "react";
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

export const CodePlaceholder = ({ code, className }: CodePlaceholderProps) => {
  const content = useMemo(() => {
    const { adapter, text } = parseCellCode(code);
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
    return nodes;
  }, [code]);
  return (
    <div
      className={cn("cm", "mo-code-placeholder", className)}
      data-testid="cell-editor-placeholder"
    >
      {content}
    </div>
  );
};
