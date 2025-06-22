/* Copyright 2024 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import type { EditorState } from "@codemirror/state";

import type { CellId } from "@/core/cells/ids";
import type { VariableName, Variables } from "@/core/variables/types";

export interface ReactiveVariableRange {
  from: number;
  to: number;
  variableName: string;
}

/**
 * Analyzes the given editor state to find variable names that represent
 * reactive dependencies from other cells (similar to ObservableHQ's approach).
 *
 * A variable is considered reactive if:
 * - It's used in the current cell
 * - It's declared by a different cell (not the current one)
 */
export function findReactiveVariables(options: {
  state: EditorState;
  cellId: CellId;
  variables: Variables;
}): ReactiveVariableRange[] {
  const tree = syntaxTree(options.state);
  const ranges: ReactiveVariableRange[] = [];

  if (!tree) {
    // No AST available yet - this can happen during initial editor setup
    // or when the language parser hasn't processed the code
    return ranges;
  }

  const cursor = tree.cursor();

  do {
    if (cursor.name === "VariableName") {
      const { from, to } = cursor;
      const variableName = options.state.doc.sliceString(
        from,
        to,
      ) as VariableName;
      if (isReactiveVariable(variableName, options)) {
        ranges.push({ from, to, variableName });
      }
    }
  } while (cursor.next());

  return ranges;
}

/**
 * Determines if a variable is reactive (declared in other cells and used in current cell).
 */
function isReactiveVariable(
  variableName: VariableName,
  context: { cellId: CellId; variables: Variables },
): boolean {
  const variable = context.variables[variableName];

  if (!variable) {
    // Variable not tracked by marimo yet - happens when cells haven't been run
    // or when referencing undefined variables
    return false;
  }

  // Variable is reactive if:
  // 1. It's declared by other cells (not the current cell)
  // We'll be more relaxed about the "used by current cell" check for now
  const declaredByOtherCells =
    variable.declaredBy.length > 0 &&
    !variable.declaredBy.includes(context.cellId);

  // For now, let's just check if it's declared by other cells
  const isReactive = declaredByOtherCells;

  return isReactive;
}
