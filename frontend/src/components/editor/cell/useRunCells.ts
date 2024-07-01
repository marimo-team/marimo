/* Copyright 2024 Marimo. All rights reserved. */
import { CellId } from "@/core/cells/ids";
import { sendRun } from "@/core/network/requests";
import { staleCellIds, useCellActions, useNotebook } from "@/core/cells/cells";
import { derefNotNull } from "@/utils/dereference";
import useEvent from "react-use-event-hook";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";
import { Logger } from "@/utils/Logger";

/**
 * Creates a function that runs all cells that have been edited or interrupted.
 */
export function useRunStaleCells() {
  const notebook = useNotebook();
  const runCells = useRunCells();
  const runStaleCells = useEvent(() => runCells(staleCellIds(notebook)));
  return runStaleCells;
}

/**
 * Creates a function that runs the cell with the given id.
 */
export function useRunCell(cellId: CellId | undefined) {
  const runCells = useRunCells();
  const runCell = useEvent(() => {
    if (cellId === undefined) {
      return;
    }
    runCells([cellId]);
  });
  return runCell;
}

/**
 * Creates a function that runs the given cells.
 */
function useRunCells() {
  const notebook = useNotebook();
  const { prepareForRun } = useCellActions();

  const runCells = useEvent(async (cellIds: CellId[]) => {
    if (cellIds.length === 0) {
      return;
    }

    const { cellHandles, cellData } = notebook;

    const codes: string[] = [];
    for (const cellId of cellIds) {
      const ref = cellHandles[cellId];
      if (ref.current) {
        codes.push(getEditorCodeAsPython(ref.current.editorView));
        ref.current.registerRun();
      } else {
        prepareForRun({ cellId });
        codes.push(cellData[cellId].code);
      }
    }

    await sendRun({ cellIds: cellIds, codes: codes }).catch((error) => {
      Logger.error(error);
    });
  });

  return runCells;
}
