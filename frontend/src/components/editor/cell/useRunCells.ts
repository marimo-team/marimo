/* Copyright 2026 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import { atom, useSetAtom } from "jotai";
import useEvent from "react-use-event-hook";
import { toast } from "@/components/ui/use-toast";
import { getNotebook } from "@/core/cells/cells";
import { useCellActions } from "@/core/cells/actions";
import type { CellId } from "@/core/cells/ids";
import { enabledCellIds, staleCellIds } from "@/core/cells/utils";
import {
  cellExecutionInputsAtom,
  cellFreshnessAtom,
  runCells,
  syncEdits,
  waitForRuntime,
} from "@/core/executions";
import { getCurrentLanguageAdapter } from "@/core/codemirror/language/commands";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";

export const hasRunAnyCellAtom = atom<boolean>(false);

/**
 * Creates a function that runs all cells that have been edited or interrupted.
 */
export function useRunStaleCells() {
  const runCells = useRunCells();
  const runStaleCells = useEvent(async () => {
    // Freshness reads the confirmed document, so an edit still in flight
    // reaches the host before the stale cells are chosen.
    const model = store.get(activeDocumentModelAtom);
    if (model === null) {
      return;
    }
    try {
      await waitForRuntime(store);
    } catch (error) {
      if (store.get(activeDocumentModelAtom) !== model) {
        return;
      }
      Logger.warn("Stale cells not run without a runtime", error);
      toast({
        title: "Failed to run",
        description: prettyError(error),
        variant: "danger",
      });
      return;
    }
    try {
      await syncEdits(model);
    } catch (error) {
      if (store.get(activeDocumentModelAtom) !== model) {
        return;
      }
      Logger.warn("Stale cells not run with unsynced edits", error);
      toast({
        title: "Edits not yet synced",
        description: "Stale cells were not run. Retry once the edits sync.",
        variant: "danger",
      });
      return;
    }
    // The request was for the notebook that was open when it was made.
    if (store.get(activeDocumentModelAtom) !== model) {
      return;
    }
    return runCells(
      staleCellIds(
        getNotebook(),
        store.get(cellExecutionInputsAtom),
        store.get(cellFreshnessAtom),
      ),
    );
  });
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
 * Creates a function that runs the given cells through the host.
 *
 * The editor settles each cell first: an open completion closes and the
 * debugger view clears, as they would on any run.
 */
export function useRunCells() {
  const { prepareForRun } = useCellActions();
  const setHasRunAnyCell = useSetAtom(hasRunAnyCellAtom);

  const runCellsMemoized = useEvent(async (cellIds: CellId[]) => {
    if (cellIds.length === 0) {
      return;
    }
    // Set a flag that a user has manually run at least one cell.
    setHasRunAnyCell(true);

    const { cellHandles } = getNotebook();
    for (const cellId of cellIds) {
      const ev = cellHandles[cellId]?.current?.editorView;
      // Skip close on markdown, since we autorun, otherwise we'll close the
      // completion each time.
      if (ev && getCurrentLanguageAdapter(ev) !== "markdown") {
        closeCompletion(ev);
      }
      prepareForRun({ cellId });
    }
    return runCells(store, cellIds);
  });

  return runCellsMemoized;
}
