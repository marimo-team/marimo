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
export function maybeAddMissingImport(
  moduleName: string,
  variableName: string,
  onAddImport: (importStatement: string) => void,
  appStore: typeof store = store,
): boolean {
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

export function maybeAddMarimoImport(
  autoRun: boolean,
  createNewCell: CellActions["createNewCell"],
): boolean {
  return maybeAddMissingImport("marimo", "mo", (importStatement) => {
    const cellId = CellId.create();
    createNewCell({
      cellId: "__end__",
      before: false,
      code: importStatement,
      lastCodeRun: autoRun ? importStatement : undefined,
      newCellId: cellId,
      autoFocus: false,
    });
    if (autoRun) {
      void sendRun([cellId], [importStatement]);
    }
  });
}
