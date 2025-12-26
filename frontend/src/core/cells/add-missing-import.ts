/* Copyright 2026 Marimo. All rights reserved. */

import { getRequestClient } from "../network/requests";
import { store } from "../state/jotai";
import { variablesAtom } from "../variables/state";
import { type CellActions, notebookAtom } from "./cells";
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
  for (const cell of cellIds.inOrderIds) {
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
 * @param createNewCell The function to create a new cell.
 * @param fromCellId The cell to add the import to.
 * @param before Whether to add the import before or after the cell.
 *
 * Returns the ID of the new cell if added, otherwise null.
 */
export function maybeAddMarimoImport({
  autoInstantiate,
  createNewCell,
  fromCellId,
  before,
}: {
  autoInstantiate: boolean;
  createNewCell: CellActions["createNewCell"];
  fromCellId?: CellId | null;
  before?: boolean;
}): CellId | null {
  const client = getRequestClient();
  let newCellId: CellId | null = null;
  const added = maybeAddMissingImport({
    moduleName: "marimo",
    variableName: "mo",
    onAddImport: (importStatement) => {
      newCellId = CellId.create();
      createNewCell({
        cellId: fromCellId ?? "__end__",
        before: before ?? false,
        code: importStatement,
        lastCodeRun: autoInstantiate ? importStatement : undefined,
        newCellId: newCellId,
        skipIfCodeExists: true,
        autoFocus: false,
      });
      if (autoInstantiate) {
        void client.sendRun({
          cellIds: [newCellId],
          codes: [importStatement],
        });
      }
    },
  });
  return added ? newCellId : null;
}

export function maybeAddAltairImport({
  autoInstantiate,
  createNewCell,
  fromCellId,
}: {
  autoInstantiate: boolean;
  createNewCell: CellActions["createNewCell"];
  fromCellId?: CellId | null;
}): CellId | null {
  const client = getRequestClient();
  let newCellId: CellId | null = null;
  const added = maybeAddMissingImport({
    moduleName: "altair",
    variableName: "alt",
    onAddImport: (importStatement) => {
      newCellId = CellId.create();
      createNewCell({
        cellId: fromCellId ?? "__end__",
        before: false,
        code: importStatement,
        lastCodeRun: autoInstantiate ? importStatement : undefined,
        newCellId: newCellId,
        skipIfCodeExists: true,
        autoFocus: false,
      });
      if (autoInstantiate) {
        void client.sendRun({
          cellIds: [newCellId],
          codes: [importStatement],
        });
      }
    },
  });
  return added ? newCellId : null;
}
