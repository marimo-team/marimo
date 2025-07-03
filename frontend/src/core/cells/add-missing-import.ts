/* Copyright 2024 Marimo. All rights reserved. */
import { sendRun } from "../network/requests";
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

export function maybeAddMarimoImport({
  autoInstantiate,
  createNewCell,
  fromCellId,
}: {
  autoInstantiate: boolean;
  createNewCell: CellActions["createNewCell"];
  fromCellId?: CellId | null;
}): boolean {
  return maybeAddMissingImport({
    moduleName: "marimo",
    variableName: "mo",
    onAddImport: (importStatement) => {
      const newCellId = CellId.create();
      createNewCell({
        cellId: fromCellId ?? "__end__",
        before: false,
        code: importStatement,
        lastCodeRun: autoInstantiate ? importStatement : undefined,
        newCellId: newCellId,
        autoFocus: false,
      });
      if (autoInstantiate) {
        void sendRun({ cellIds: [newCellId], codes: [importStatement] });
      }
    },
  });
}

export function maybeAddAltairImport({
  autoInstantiate,
  createNewCell,
  fromCellId,
}: {
  autoInstantiate: boolean;
  createNewCell: CellActions["createNewCell"];
  fromCellId?: CellId | null;
}): boolean {
  return maybeAddMissingImport({
    moduleName: "altair",
    variableName: "alt",
    onAddImport: (importStatement) => {
      const newCellId = CellId.create();
      createNewCell({
        cellId: fromCellId ?? "__end__",
        before: false,
        code: importStatement,
        lastCodeRun: autoInstantiate ? importStatement : undefined,
        newCellId: newCellId,
        autoFocus: false,
      });
      if (autoInstantiate) {
        void sendRun({ cellIds: [newCellId], codes: [importStatement] });
      }
    },
  });
}
