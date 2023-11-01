/* Copyright 2023 Marimo. All rights reserved. */
import { RuntimeState } from "@/core/RuntimeState";
import { CellRuntimeState } from "@/core/model/cells";
import { CellId } from "@/core/model/ids";
import { sendRunMultiple } from "@/core/network/requests";
import { useCells } from "@/core/state/cells";
import { derefNotNull } from "@/utils/dereference";
import useEvent from "react-use-event-hook";

/**
 * Creates a function that runs all cells that have been edited or interrupted.
 */
export function useRunStaleCells() {
  const cells = useCells();
  const runCells = useRunCells();

  const runStaleCells = useEvent(async () => {
    const staleCells = cells.present.filter((cell) => {
      return cell.edited || cell.interrupted;
    });
    await runCells(staleCells);
  });

  return runStaleCells;
}

/**
 * Creates a function that runs the cell with the given id.
 */
export function useRunCell(cellId: CellId) {
  const cells = useCells();
  const runCells = useRunCells();

  const runCell = useEvent(async () => {
    const cell = cells.present.find((cell) => cell.key === cellId);
    if (cell) {
      await runCells([cell]);
    }
  });

  return runCell;
}

/**
 * Creates a function that runs the given cells.
 */
export function useRunCells() {
  const runCells = useEvent(async (cells: CellRuntimeState[]) => {
    if (cells.length === 0) {
      return;
    }

    const cellIds: CellId[] = [];
    const codes: string[] = [];
    for (const cell of cells) {
      const ref = derefNotNull(cell.ref);

      cellIds.push(cell.key);
      codes.push(ref.editorView.state.doc.toString());

      ref.registerRun();
    }

    RuntimeState.INSTANCE.registerRunStart();
    await sendRunMultiple(cellIds, codes);
  });

  return runCells;
}
