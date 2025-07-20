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

function buildCellGraph(
  cellIds: CellId[],
  variables: Variables,
): Record<CellId, CellGraph> {
  // First pass: build direct connections
  const connections = new Map<
    CellId,
    {
      variables: Set<VariableName>;
      parents: Set<CellId>;
      children: Set<CellId>;
    }
  >();
  for (const cellId of cellIds) {
    connections.set(cellId, {
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
      connections.get(declarer)?.variables.add(variable.name);
      for (const user of variable.usedBy) {
        if (declarer !== user) {
          connections.get(user)?.parents.add(declarer);
          connections.get(declarer)?.children.add(user);
        }
      }
    }
  }

  // Second pass: build final graph with transitive closures
  const graphs: Record<CellId, CellGraph> = {};

  for (const cellId of cellIds) {
    const conn = connections.get(cellId);
    if (!conn) {
      continue;
    }

    const ancestors = computeTransitiveClosure(
      cellId,
      (id) => connections.get(id)?.parents ?? new Set(),
    );
    const descendants = computeTransitiveClosure(
      cellId,
      (id) => connections.get(id)?.children ?? new Set(),
    );

    graphs[cellId] = {
      parents: conn.parents,
      children: conn.children,
      ancestors,
      descendants,
      variables: [...conn.variables],
    };
  }

  return graphs;
}

export const cellGraphsAtom = atom((get) => {
  const notebook = get(notebookAtom);
  const variables = get(variablesAtom);
  return buildCellGraph(notebook.cellIds.inOrderIds, variables);
});

export function isVariableInSelectedDataflow(
  variable: Variable,
  selected: {
    cellId: CellId;
    graph: {
      ancestors: ReadonlySet<CellId>;
      descendants: ReadonlySet<CellId>;
    };
  },
): boolean {
  // Variable is used by the selected cell
  if (variable.usedBy.includes(selected.cellId)) {
    return true;
  }

  // Variable is declared by the selected cell and used by someone
  if (
    variable.declaredBy.includes(selected.cellId) &&
    variable.usedBy.length > 0
  ) {
    return true;
  }

  // Variable flows through the selected cell:
  // It must be declared by an ancestor AND used by the selected cell or a descendant
  const isDeclaredByAncestor = variable.declaredBy.some((declarer) =>
    selected.graph.ancestors.has(declarer),
  );

  if (isDeclaredByAncestor) {
    // Only highlight if this variable is actually used by selected cell or its descendants
    return (
      variable.usedBy.includes(selected.cellId) ||
      variable.usedBy.some((user) => selected.graph.descendants.has(user))
    );
  }

  return false;
}
