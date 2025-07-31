/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { getAllEditorViews, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { variablesAtom } from "@/core/variables/state";
import type { Variables } from "@/core/variables/types";
import { Objects } from "@/utils/objects";
import { getEditorCodeAsPython } from "../language/utils";

export function getCodes(otherCode: string) {
  const codes = getOtherCellsCode(otherCode);

  return [...codes, otherCode].join("\n");
}

export function getOtherCellsCode(otherCode: string) {
  // Get all other cells' code
  // Put `import` statements at the top, as it can help copilot give better suggestions
  // TODO: we should sort this topologically
  const codes = getAllEditorViews()
    .map((editorView) => {
      const code = getEditorCodeAsPython(editorView);
      if (code === otherCode) {
        return null;
      }
      return code;
    })
    .filter(Boolean)
    .sort((a, b) => {
      if (a.startsWith("import") && !b.startsWith("import")) {
        return -1;
      }
      if (!a.startsWith("import") && b.startsWith("import")) {
        return 1;
      }
      return 0;
    });

  return codes;
}

const notebookCellCodes = atom((get) => {
  const notebook = get(notebookAtom);
  const codes = Objects.fromEntries(
    notebook.cellIds.inOrderIds.map((id) => {
      const handle = notebook.cellHandles[id];
      return [
        id,
        handle?.current ? getEditorCodeAsPython(handle.current.editorView) : "",
      ];
    }),
  );
  return codes;
});
const inOrderCellIdsAtom = atom((get) => {
  const notebook = get(notebookAtom);
  return notebook.cellIds.inOrderIds;
});
const topologicalCellIdsAtom = atom((get) => {
  const cellIds = get(inOrderCellIdsAtom);
  const variables = get(variablesAtom);
  return getTopologicalCellIds(cellIds, variables);
});

export const topologicalCodesAtom = atom((get) => {
  const sortedCellIds = get(topologicalCellIdsAtom);
  const codes = get(notebookCellCodes);
  return { cellIds: sortedCellIds, codes };
});

export function getTopologicalCellIds(cellIds: CellId[], variables: Variables) {
  // Build adjacency list
  const adjacency = new Map<CellId, CellId[]>();
  cellIds.forEach((id) => adjacency.set(id, []));

  // Start with all cells with no declaredBy or usedBy
  const noDepCells = new Set<CellId>(cellIds); // Cells with no declaredBy
  const noUsedByCells = new Set<CellId>(cellIds); // Cells with no usedBy

  // Link "declaredBy -> usedBy"
  for (const { declaredBy, usedBy } of Object.values(variables)) {
    for (const declCell of declaredBy) {
      noDepCells.delete(declCell);
      for (const useCell of usedBy) {
        noUsedByCells.delete(useCell);

        if (useCell !== declCell) {
          adjacency.get(declCell)?.push(useCell);
        }
      }
    }
  }

  // Kahn's algorithm for topological sort
  const inDegree = new Map<CellId, number>();
  cellIds.forEach((id) => inDegree.set(id, 0));

  adjacency.forEach((targets) => {
    targets.forEach((t) => {
      inDegree.set(t, (inDegree.get(t) || 0) + 1);
    });
  });

  const queue: CellId[] = [];
  inDegree.forEach((deg, id) => {
    if (deg === 0) {
      queue.push(id);
    }
  });

  const sorted: CellId[] = [];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      break;
    }
    sorted.push(current);
    adjacency.get(current)?.forEach((t) => {
      inDegree.set(t, (inDegree.get(t) || 0) - 1);
      if (inDegree.get(t) === 0) {
        queue.push(t);
      }
    });
  }

  // Put noDepCells at the end
  const filteredSorted = sorted.filter((id) => !noDepCells.has(id));
  return [...filteredSorted, ...noDepCells];
}
