/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import { sendRun } from "@/core/network/requests";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import useEvent from "react-use-event-hook";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";
import { Logger } from "@/utils/Logger";
import { staleCellIds } from "@/core/cells/utils";
import { useAtomValue } from "jotai";
import { autoInstantiateAtom } from "@/core/config/config";

/**
 * Creates a function that runs all cells that have been edited or interrupted.
 */
export function useRunStaleCells() {
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const runCells = useRunCells();
  const runStaleCells = useEvent(() =>
    runCells(staleCellIds(getNotebook(), autoInstantiate)),
  );
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
  const { prepareForRun } = useCellActions();

  const runCells = useEvent(async (cellIds: CellId[]) => {
    if (cellIds.length === 0) {
      return;
    }

    const { cellHandles, cellData } = getNotebook();

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
