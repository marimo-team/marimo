/* Copyright 2024 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import useEvent from "react-use-event-hook";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { enabledCellIds, staleCellIds } from "@/core/cells/utils";
import { getCurrentLanguageAdapter } from "@/core/codemirror/language/commands";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";
import { sendRun } from "@/core/network/requests";
import { Logger } from "@/utils/Logger";

/**
 * Creates a function that runs all cells that have been edited or interrupted.
 */
export function useRunStaleCells() {
  const runCells = useRunCells();
  const runStaleCells = useEvent(() => runCells(staleCellIds(getNotebook())));
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

export function useRunAllCells() {
  const runCells = useRunCells();
  const runAllCells = useEvent(() => runCells(enabledCellIds(getNotebook())));
  return runAllCells;
}

/**
 * Creates a function that runs the given cells.
 */
function useRunCells() {
  const { prepareForRun } = useCellActions();

  const runCells = useEvent(async (cellIds: CellId[]) => {
    if (cellIds.length === 0) {
      return;
    }

    const { cellHandles, cellData } = getNotebook();

    const codes: string[] = [];
    for (const cellId of cellIds) {
      const ref = cellHandles[cellId];
      const ev = ref?.current?.editorView;
      let code: string;
      // Performs side-effects that must run whenever the cell is run, but doesn't
      // actually run the cell.
      if (ev) {
        // Skip close on markdown, since we autorun, otherwise we'll close the
        // completion each time.
        if (getCurrentLanguageAdapter(ev) !== "markdown") {
          closeCompletion(ev);
        }
        // Prefer code from editor
        code = getEditorCodeAsPython(ev);
      } else {
        code = cellData[cellId].code || "";
      }

      codes.push(code);
      prepareForRun({ cellId });
    }

    // Send the run request to the Kernel
    await sendRun({ cellIds: cellIds, codes: codes }).catch((error) => {
      Logger.error(error);
    });
  });

  return runCells;
}
