/* Copyright 2024 Marimo. All rights reserved. */

import type { SyntaxNode, Tree } from "@lezer/common";
import { parser } from "@lezer/python";

function getLastStatement(tree: Tree): SyntaxNode | null {
  let lastStmt: SyntaxNode | null = null;
  const cursor = tree.cursor();

  do {
    if (cursor.name === "ExpressionStatement") {
      lastStmt = cursor.node;
    }
  } while (cursor.next());

  return lastStmt;
}

export function wrapInFunction(code: string) {
  const lines = code.split("\n");
  const indentation = "    ";

  const tree = parser.parse(code);
  const lastStmt = getLastStatement(tree);

  if (!lastStmt) {
    return [
      "def _():",
      ...indentLines(lines, indentation),
      `${indentation}return`,
      "",
      "",
      "_()",
    ].join("\n");
  }

  const codeBeforeLastStmt = code.slice(0, lastStmt.from).trim();
  const codeRest = code.slice(lastStmt.from).trim();
  const linesBeforeLastStmt = codeBeforeLastStmt.split("\n");
  const linesRest = codeRest.split("\n");

  return [
    "def _():",
    ...indentLines(linesBeforeLastStmt, indentation),
    `${indentation}return ${linesRest[0]}`,
    ...indentLines(linesRest.slice(1), indentation),
    "",
    "",
    "_()",
  ].join("\n");
}

function indentLines(lines: string[], indentation: string): string[] {
  if (lines.length === 1 && lines[0] === "") {
    return [];
  }

  const indentedLines = [];
  for (const line of lines) {
    if (line === "") {
      indentedLines.push("");
    } else {
      indentedLines.push(indentation + line);
    }
  }
  return indentedLines;
}
