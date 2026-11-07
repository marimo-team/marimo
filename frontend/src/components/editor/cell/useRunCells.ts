/* Copyright 2026 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import { atom, useSetAtom } from "jotai";
import useEvent from "react-use-event-hook";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, type NotebookState } from "@/core/cells/cells";
import { useCellActions } from "@/core/cells/actions";
import type { CellId } from "@/core/cells/ids";
import { enabledCellIds, staleCellIds } from "@/core/cells/utils";
import {
  cellExecutionInputsAtom,
  cellFreshnessAtom,
  submitCells,
  withdrawCells,
} from "@/core/executions";
import { getCurrentLanguageAdapter } from "@/core/codemirror/language/commands";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";
import { useRequestClient } from "@/core/network/requests";
import type { ExecuteCellsRequest } from "@/core/network/types";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { store } from "@/core/state/jotai";
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
    try {
      await model?.flush();
    } catch (error) {
      if (store.get(activeDocumentModelAtom) !== model) {
        return;
      }
      Logger.warn("Running stale cells with unsynced edits", error);
      toast({
        title: "Edits not yet synced",
        description: "Stale cells were chosen from the last synced source.",
        variant: "danger",
      });
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
 * Creates a function that runs the given cells.
 */
export function useRunCells() {
  const { prepareForRun } = useCellActions();
  const { sendRun } = useRequestClient();
  const setHasRunAnyCell = useSetAtom(hasRunAnyCellAtom);

  const runCellsMemoized = useEvent(async (cellIds: CellId[]) => {
    if (cellIds.length === 0) {
      return;
    }

    const notebook = getNotebook();

    // Set a flag that a user has manually run at least one cell.
    setHasRunAnyCell(true);

    return runCells({ cellIds, sendRun, prepareForRun, notebook });
  });

  return runCellsMemoized;
}

export async function runCells({
  cellIds,
  sendRun,
  prepareForRun,
  notebook,
}: {
  cellIds: CellId[];
  sendRun: (request: ExecuteCellsRequest) => Promise<null>;
  prepareForRun: (action: { cellId: CellId }) => void;
  notebook: NotebookState;
}) {
  if (cellIds.length === 0) {
    return;
  }

  const { cellHandles, cellData } = notebook;

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
      code = cellData[cellId]?.code || "";
    }

    codes.push(code);
    prepareForRun({ cellId });
  }
  // The kernel sets a disabled cell aside without planning an execution,
  // so a submission for it would never be superseded.
  submitCells(
    store,
    cellIds.filter((cellId) => !cellData[cellId]?.config.disabled),
  );

  // TODO(MO-8346): Submit through the host's `runtime.run`.
  await sendRun({ cellIds: cellIds, codes: codes }).catch((error) => {
    withdrawCells(store, cellIds);
    Logger.error(error);
  });
}
