/* Copyright 2026 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { SyntaxNode } from "@lezer/common";
import { parser } from "@lezer/python";
import { cellActionsState } from "../cells/state";

export function pasteBundle(): Extension[] {
  return [
    EditorView.domEventHandlers({
      paste: (event: ClipboardEvent, view: EditorView) => {
        const text = event.clipboardData?.getData("text/plain");
        if (!text || !looksLikeMarimoApp(text)) {
          return false;
        }

        const { setup, cells } = extractMarimoApp(text);
        if (setup === null && cells.length === 0) {
          return false;
        }

        const actions = view.state.facet(cellActionsState);
        // The `with app.setup` block belongs in the special setup cell, not in
        // an ordinary cell.
        if (setup !== null) {
          actions.addOrAppendSetupCell(setup);
        }
        if (cells.length > 0) {
          actions.createManyBelow(cells);
        }
        return true;
      },
    }),
  ];
}

/** Whether the pasted text looks like marimo app source worth parsing. */
function looksLikeMarimoApp(text: string): boolean {
  return /@app\.cell|@app\.function|\bapp\.setup\b/.test(text);
}

export interface ExtractedApp {
  /** The `with app.setup` block's body, if present. Belongs in the setup cell. */
  setup: string | null;
  /** Ordinary cells, in source order. */
  cells: string[];
}

/**
 * Extract the cells of a marimo app from its source.
 *
 * Parses the pasted source with the Python grammar (the same one that powers
 * the editor) and turns each marimo construct into a cell:
 * - `with app.setup(...)` contributes the setup block's body, returned
 *   separately as `setup` because it belongs in the dedicated setup cell.
 * - `@app.cell` functions contribute their body, minus the trailing
 *   auto-generated `return`.
 * - `@app.function` definitions contribute the whole function (the decorator
 *   is dropped, but the function — including its `return` — is kept).
 *
 * Using the real syntax tree means decorators, `async def`, multi-line
 * signatures, nested functions, and multi-line returns of any bracket type are
 * all handled structurally rather than by line-based heuristics.
 */
export function extractMarimoApp(text: string): ExtractedApp {
  if (!looksLikeMarimoApp(text)) {
    return { setup: null, cells: [] };
  }

  const cells: string[] = [];
  const setupBlocks: string[] = [];
  const tree = parser.parse(text);

  // A node's `from` starts after its line's leading indentation; extend back to
  // the start of the line so `dedent` sees consistent indentation, then dedent.
  const blockText = (from: number, to: number): string => {
    const lineStart = text.lastIndexOf("\n", from - 1) + 1;
    return dedent(text.slice(lineStart, to));
  };

  const pushCell = (from: number, to: number) => {
    const cell = blockText(from, to);
    if (cell.trim()) {
      cells.push(cell);
    }
  };

  // The text of a block's body (the statements after its `:`), optionally
  // dropping a trailing auto-generated `return`. Returns null if empty.
  const bodyText = (
    body: SyntaxNode,
    stripTrailingReturn: boolean,
  ): string | null => {
    const children: SyntaxNode[] = [];
    for (let child = body.firstChild; child; child = child.nextSibling) {
      if (child.name !== ":") {
        children.push(child);
      }
    }
    if (stripTrailingReturn && children.at(-1)?.name === "ReturnStatement") {
      children.pop();
    }
    const first = children[0];
    const last = children.at(-1);
    if (!first || !last) {
      return null;
    }
    const cell = blockText(first.from, last.to);
    return cell.trim() ? cell : null;
  };

  tree.iterate({
    enter: (node) => {
      // Setup cell: `with app.setup:` / `with app.setup(...):`
      if (node.name === "WithStatement") {
        const body = node.node.getChild("Body");
        if (body && text.slice(node.from, body.from).includes("app.setup")) {
          const setup = bodyText(body, false);
          if (setup !== null) {
            setupBlocks.push(setup);
          }
        }
        return false;
      }

      if (node.name !== "DecoratedStatement") {
        // Keep descending until we reach the decorated definitions.
        return true;
      }

      const decorator = node.node.getChild("Decorator");
      const fn = node.node.getChild("FunctionDefinition");
      if (!decorator || !fn) {
        return false;
      }
      const decoratorText = text.slice(decorator.from, decorator.to).trim();

      // `@app.cell` / `@app.cell(...)`: the body becomes a cell, minus the
      // trailing auto-generated return.
      if (decoratorText.startsWith("@app.cell")) {
        const body = fn.getChild("Body");
        if (body) {
          const cell = bodyText(body, true);
          if (cell !== null) {
            cells.push(cell);
          }
        }
        return false;
      }

      // `@app.function`: the whole function definition is the cell (the
      // decorator is dropped, but the function — including its return — stays).
      if (decoratorText.startsWith("@app.function")) {
        pushCell(fn.from, fn.to);
      }

      return false;
    },
  });

  return {
    setup: setupBlocks.length > 0 ? setupBlocks.join("\n\n") : null,
    cells,
  };
}

/**
 * Convenience wrapper returning only the ordinary cells (excluding the setup
 * block). Prefer {@link extractMarimoApp} when the setup block matters.
 */
export function extractCells(text: string): string[] {
  return extractMarimoApp(text).cells;
}

function dedent(text: string): string {
  const lines = text.split("\n");
  if (lines.length === 0) {
    return "";
  }

  // Cache non-empty lines
  const nonEmptyLines = lines.filter((line) => line.trim().length > 0);
  if (nonEmptyLines.length === 0) {
    return "";
  }

  const leadingSpaceRegex = /^\s*/;
  const minIndent = Math.min(
    ...nonEmptyLines.map(
      (line) =>
        line.match(leadingSpaceRegex)?.[0].length ?? Number.POSITIVE_INFINITY,
    ),
  );

  return minIndent === 0
    ? text.trim()
    : lines
        .map((line) => line.slice(minIndent))
        .join("\n")
        .trim();
}
