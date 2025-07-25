/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { variablesAtom } from "@/core/variables/state";
import type { Variable, VariableName, Variables } from "@/core/variables/types";

export interface CellGraph {
  variables: readonly VariableName[];

  // Direct connections for traversal
  parents: ReadonlySet<CellId>; // Cells I depend on (direct upstream)
  children: ReadonlySet<CellId>; // Cells that depend on me (direct downstream)

  // Pre-computed transitive closure
  ancestors: ReadonlySet<CellId>; // All cells upstream (includes parents)
  descendants: ReadonlySet<CellId>; // All cells downstream (includes children)
}

function computeTransitiveClosure(
  cellId: CellId,
  getDirectConnections: (id: CellId) => Set<CellId>,
  visited = new Set<CellId>(),
): Set<CellId> {
  if (visited.has(cellId)) {
    return new Set();
  }
  visited.add(cellId);

  const result = new Set<CellId>();
  for (const connectedId of getDirectConnections(cellId)) {
    result.add(connectedId);
    for (const id of computeTransitiveClosure(
      connectedId,
      getDirectConnections,
      visited,
    )) {
      result.add(id);
    }
  }

  return result;
}

export function buildCellGraph(
  cellIds: CellId[],
  variables: Variables,
): Record<CellId, CellGraph> {
  // First pass: build direct connections
  const dependencyMap = new Map<
    CellId,
    {
      variables: Set<VariableName>;
      parents: Set<CellId>;
      children: Set<CellId>;
    }
  >();
  for (const cellId of cellIds) {
    dependencyMap.set(cellId, {
      variables: new Set(),
      parents: new Set(),
      children: new Set(),
    });
  }
  // get parent-child relationships from variables
  for (const variable of Object.values(variables)) {
    if (variable.dataType === "module") {
      // skip modules
      continue;
    }
    for (const declarer of variable.declaredBy) {
      dependencyMap.get(declarer)?.variables.add(variable.name);
      for (const user of variable.usedBy) {
        if (declarer !== user) {
          dependencyMap.get(user)?.parents.add(declarer);
          dependencyMap.get(declarer)?.children.add(user);
        }
      }
    }
  }

  // Second pass: build final graph with transitive closures
  const graphs: Record<CellId, CellGraph> = {};
  for (const [cellId, cellDeps] of dependencyMap.entries()) {
    graphs[cellId] = {
      parents: cellDeps.parents,
      children: cellDeps.children,
      variables: [...cellDeps.variables],
      ancestors: computeTransitiveClosure(
        cellId,
        (id) => dependencyMap.get(id)?.parents ?? new Set(),
      ),
      descendants: computeTransitiveClosure(
        cellId,
        (id) => dependencyMap.get(id)?.children ?? new Set(),
      ),
    };
  }

  return graphs;
}

export const cellGraphsAtom = atom((get) => {
  const notebook = get(notebookAtom);
  const variables = get(variablesAtom);
  return buildCellGraph(notebook.cellIds.inOrderIds, variables);
});

/**
 * Determines if a variable should be highlighted when a cell is selected.
 *
 * For upstream dataflow: We can precisely track which variables flow INTO the selected cell
 * by checking what the selected cell actually uses.
 *
 * For downstream dataflow: We only have cell-level dependency information, not variable-level,
 * so we highlight ALL variables in descendant cells since they will all be re-executed
 * when the selected cell changes.
 *
 * @param variable - The variable to check for highlighting
 * @param options - The currently selected cell and its dependency graph
 */
export function isVariableAffectedBySelectedCell(
  variable: Variable,
  selectedCell?: { id: CellId; graph: CellGraph },
): boolean {
  if (!selectedCell) {
    return false;
  }

  // Case 1: Variable is used by the selected cell (incoming dataflow)
  if (variable.usedBy.includes(selectedCell.id)) {
    return true;
  }

  // Case 2: Variable is declared by the selected cell (outgoing dataflow)
  if (variable.declaredBy.includes(selectedCell.id)) {
    return true;
  }

  // Case 3: Variable is declared by an ancestor AND used by selected cell or descendants
  // This captures the flow-through case
  const isDeclaredByAncestor = variable.declaredBy.some((declarer) =>
    selectedCell.graph.parents.has(declarer),
  );

  if (isDeclaredByAncestor) {
    return variable.usedBy.some((user) => selectedCell.graph.parents.has(user));
  }

  // Case 4: Variable is declared by a descendant
  // These will be re-executed when the selected cell changes
  const isDeclaredByDescendant = variable.declaredBy.some((declarer) =>
    selectedCell.graph.children.has(declarer),
  );

  if (isDeclaredByDescendant) {
    return true;
  }

  return false;
}
