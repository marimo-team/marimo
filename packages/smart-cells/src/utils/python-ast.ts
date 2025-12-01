/* Copyright 2024 Marimo. All rights reserved. */

import type { SyntaxNode, TreeCursor } from "@lezer/common";
import { parser } from "@lezer/python";

/**
 * Parse Python code into an AST.
 */
export function parsePythonAST(code: string) {
  return parser.parse(code);
}

/**
 * Parsed function argument lists (positional and keyword arguments).
 */
export interface ParsedArgs {
  args: SyntaxNode[];
  kwargs: Array<{ key: string; value: string }>;
}

const SYNTAX_TOKENS = new Set(["(", "[", "{", ",", ")", "]", "}"]);

/**
 * Parse an ArgList node into positional and keyword arguments.
 *
 * @param argCursor - A cursor positioned at an ArgList node
 * @param code - The source code
 * @returns Parsed positional and keyword arguments
 */
export function parseArgsKwargs(
  argCursor: TreeCursor,
  code: string,
): ParsedArgs {
  if (argCursor.name !== "ArgList") {
    // biome-ignore lint/suspicious/noConsole: useful for debugging AST parsing issues
    console.warn(`Not an ArgList, name: ${argCursor.name}`);
    return { args: [], kwargs: [] };
  }

  return {
    args: parseArgs(argCursor),
    kwargs: parseKwargs(argCursor, code),
  };
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

/**
 * Get the content of a String or FormatString node.
 *
 * @param node - The String or FormatString node
 * @param code - The source code
 * @returns The string content, or null if not a string node
 */
export function getStringContent(
  node: SyntaxNode,
  code: string,
): string | null {
  // Handle triple quoted strings
  if (node.name === "String") {
    const content = code.slice(node.from, node.to);
    // Handle r-strings with triple quotes
    if (content.startsWith('r"""') || content.startsWith("r'''")) {
      return content.slice(4, -3);
    }
    // Handle regular triple quotes
    if (content.startsWith('"""') || content.startsWith("'''")) {
      return content.slice(3, -3);
    }
    // Handle r-strings with single quotes
    if (content.startsWith('r"') || content.startsWith("r'")) {
      return content.slice(2, -1);
    }
    // Handle single quoted strings
    return content.slice(1, -1);
  }

  // Handle f-strings
  if (node.name === "FormatString") {
    const content = code.slice(node.from, node.to);
    if (content.startsWith('f"""') || content.startsWith("f'''")) {
      return content.slice(4, -3);
    }
    if (content.startsWith('rf"""') || content.startsWith("rf'''")) {
      return content.slice(5, -3);
    }
    if (content.startsWith('fr"""') || content.startsWith("fr'''")) {
      return content.slice(5, -3);
    }
    if (content.startsWith('r"""') || content.startsWith("r'''")) {
      return content.slice(4, -3);
    }
    // Single quotes
    if (content.startsWith('f"') || content.startsWith("f'")) {
      return content.slice(2, -1);
    }
    if (content.startsWith('rf"') || content.startsWith("rf'")) {
      return content.slice(3, -1);
    }
    if (content.startsWith('fr"') || content.startsWith("fr'")) {
      return content.slice(3, -1);
    }
    if (content.startsWith('r"') || content.startsWith("r'")) {
      return content.slice(2, -1);
    }
    return content.slice(2, -1);
  }

  return null;
}

/**
 * Get the length of the quote prefix in a string (e.g., 'f"""' -> 4).
 */
export function getPrefixLength(code: string): number {
  if (code === "") {
    return 0;
  }
  if (code.startsWith('rf"""') || code.startsWith("rf'''")) {
    return 5;
  }
  if (code.startsWith('fr"""') || code.startsWith("fr'''")) {
    return 5;
  }
  if (code.startsWith('f"""') || code.startsWith("f'''")) {
    return 4;
  }
  if (code.startsWith('r"""') || code.startsWith("r'''")) {
    return 4;
  }
  if (code.startsWith('"""') || code.startsWith("'''")) {
    return 3;
  }
  if (code.startsWith("rf'") || code.startsWith('rf"')) {
    return 3;
  }
  if (code.startsWith("fr'") || code.startsWith('fr"')) {
    return 3;
  }
  if (code.startsWith("f'") || code.startsWith('f"')) {
    return 2;
  }
  if (code.startsWith("r'") || code.startsWith('r"')) {
    return 2;
  }
  if (code.startsWith("'") || code.startsWith('"')) {
    return 1;
  }
  return 0;
}
