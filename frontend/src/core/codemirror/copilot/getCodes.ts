/* Copyright 2024 Marimo. All rights reserved. */
import { getAllEditorViews, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
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

export function getTopologicalCellIds() {
  const notebook = store.get(notebookAtom);
  const variables = store.get(variablesAtom);
  const cellIds = notebook.cellIds.inOrderIds;

  // Build adjacency list
  const adjacency = new Map<CellId, CellId[]>();
  cellIds.forEach((id) => adjacency.set(id, []));

  // Link "declaredBy -> usedBy"
  for (const { declaredBy, usedBy } of Object.values(variables)) {
    if (!declaredBy || !usedBy) {
      continue;
    }
    const declArr = Array.isArray(declaredBy) ? declaredBy : [declaredBy];
    declArr.forEach((declCell) => {
      usedBy.forEach((useCell) => {
        if (useCell !== declCell) {
          adjacency.get(declCell)?.push(useCell);
        }
      });
    });
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

  return sorted;
}

export function getTopologicalCodes(): {
  cellIds: CellId[];
  codes: Record<CellId, string>;
} {
  const cellIds = getTopologicalCellIds();
  const notebook = store.get(notebookAtom);
  const codes = Objects.fromEntries(
    cellIds.map((id) => {
      const handle = notebook.cellHandles[id];
      return [
        id,
        handle?.current ? getEditorCodeAsPython(handle.current.editorView) : "",
      ];
    }),
  );

  return { cellIds, codes };
}
