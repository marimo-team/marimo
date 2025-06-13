/* Copyright 2024 Marimo. All rights reserved. */

import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { Logger } from "@/utils/Logger";

const SYNTAX_TOKENS = new Set(["(", "[", "{", ",", ")", "]", "}"]);

export function parseArgsKwargs(
  argCursor: TreeCursor,
  code: string,
): {
  args: SyntaxNode[];
  kwargs: Array<{ key: string; value: string }>;
} {
  // Check we are in an ArgList
  const name = argCursor.name;

  if (name !== "ArgList") {
    Logger.warn(`Not an ArgList, name: ${name}`);
    return { args: [], kwargs: [] };
  }

  return { args: parseArgs(argCursor), kwargs: parseKwargs(argCursor, code) };
}

function parseArgs(argCursor: TreeCursor): SyntaxNode[] {
  // Move to first argument
  argCursor.firstChild();

  const args: SyntaxNode[] = [];
  let name = argCursor.name;

  do {
    name = argCursor.name;
    if (SYNTAX_TOKENS.has(name)) {
      continue;
    }

    if (name === "VariableName") {
      // Stop if we hit a kwarg (next token is AssignOp)
      const peek = argCursor.node.nextSibling;
      if (peek?.name === "AssignOp") {
        argCursor.prev();
        break;
      }
    }

    args.push(argCursor.node);
  } while (argCursor.nextSibling());

  return args;
}

function parseKwargs(
  argCursor: TreeCursor,
  code: string,
): Array<{ key: string; value: string }> {
  const kwargs: Array<{ key: string; value: string }> = [];
  let name = argCursor.name;

  do {
    name = argCursor.name;
    if (name === "VariableName") {
      const key = code.slice(argCursor.from, argCursor.to);

      // Check for AssignOp
      const assignNode = argCursor.node.nextSibling;
      if (!assignNode || assignNode.name !== "AssignOp") {
        continue;
      }

      // Get the value node
      const valueNode = assignNode.nextSibling;
      if (!valueNode) {
        continue;
      }

      const value = code.slice(valueNode.from, valueNode.to).trim();
      kwargs.push({ key, value });
    }
  } while (argCursor.nextSibling());

  return kwargs;
}
