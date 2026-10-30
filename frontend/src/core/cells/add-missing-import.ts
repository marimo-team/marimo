/* Copyright 2026 Marimo. All rights reserved. */

import { getRequestClient } from "../network/requests";
import { store } from "../state/jotai";
import { variablesAtom } from "../variables/state";
import { notebookAtom } from "./cells";
import type { CreateCell, CreateCellOptions } from "./actions";
import { CellId } from "./ids";

/**
 * Checks if any Python imports are missing from the current file and adds them if necessary.
 * @param moduleName The name of the module to import.
 * @param variableName The name of the variable to import.
 */
export function maybeAddMissingImport({
  moduleName,
  variableName,
  onAddImport,
  appStore = store,
}: {
  moduleName: string;
  variableName: string;
  onAddImport: (importStatement: string) => void;
  appStore?: typeof store;
}): boolean {
  // If variableName is already in the variables state,
  // then the import is not missing (or the name has been taken).
  const variables = appStore.get(variablesAtom);
  if (variableName in variables) {
    return false;
  }

  // Check if the import statement already exists in the notebook.
  const { cellData, cellIds } = appStore.get(notebookAtom);
  const regex = new RegExp(
    `import[ \t]+${moduleName}[ \t]+as[ \t]+${variableName}`,
    "g",
  );
  for (const cell of cellIds) {
    if (regex.test(cellData[cell].code)) {
      return false;
    }
  }

  const importStatement = `import ${moduleName} as ${variableName}`;
  onAddImport(importStatement);

  return true;
}

/**
 * Adds a marimo import to the notebook if not already present.
 * @param autoInstantiate Whether to automatically run the cell.
 * @param createCell The command that creates a cell.
 * @param fromCellId The cell to add the import next to.
 * @param before Whether to add the import before or after the cell.
 *
 * Returns the ID of the new cell if added, otherwise null.
 */
export function maybeAddMarimoImport({
  autoInstantiate,
  createCell,
  fromCellId,
  before,
}: {
  autoInstantiate: boolean;
  createCell: CreateCell;
  fromCellId?: CellId | null;
  before?: boolean;
}): CellId | null {
  return addImport({
    moduleName: "marimo",
    variableName: "mo",
    autoInstantiate,
    createCell,
    placement: before ? { before: fromCellId } : { after: fromCellId },
  });
}

export function maybeAddAltairImport({
  autoInstantiate,
  createCell,
  fromCellId,
}: {
  autoInstantiate: boolean;
  createCell: CreateCell;
  fromCellId?: CellId | null;
}): CellId | null {
  return addImport({
    moduleName: "altair",
    variableName: "alt",
    autoInstantiate,
    createCell,
    placement: { after: fromCellId },
  });
}

/** Create the import cell, and run it when the notebook runs on its own. */
function addImport({
  moduleName,
  variableName,
  autoInstantiate,
  createCell,
  placement,
}: {
  moduleName: string;
  variableName: string;
  autoInstantiate: boolean;
  createCell: CreateCell;
  placement: Pick<CreateCellOptions, "after" | "before">;
}): CellId | null {
  let newCellId: CellId | null = null;
  maybeAddMissingImport({
    moduleName,
    variableName,
    onAddImport: (importStatement) => {
      const id = CellId.create();
      const created = createCell({
        ...placement,
        id,
        code: importStatement,
        skipIfCodeExists: true,
        focus: false,
      });
      newCellId = created === null ? null : id;
      if (autoInstantiate && newCellId !== null) {
        void getRequestClient().sendRun({
          cellIds: [newCellId],
          codes: [importStatement],
        });
      }
    },
  });
  return newCellId;
}
