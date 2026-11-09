/* Copyright 2026 Marimo. All rights reserved. */

/** Submit cell runs to the host. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { createStore } from "jotai";
import type { DocumentModel } from "@/core/notebook/document";
import { toast } from "@/components/ui/use-toast";
import { startRuntimeIfLazy } from "@/core/runtime/config";
import {
  activeDocumentModelAtom,
  activeNotebookBackendAtom,
} from "@/core/session/active-notebook";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import {
  acceptRun,
  submitCells,
  waitForRuntimeRunning,
  withdrawCells,
} from "./atoms";

type Store = ReturnType<typeof createStore>;

/**
 * Start a lazy runtime and wait until the host reports it running.
 *
 * The host refuses a run while its runtime is not running, so a request
 * made during startup waits here instead of failing. It rejects once the
 * runtime cannot come up, so the request is not left waiting.
 */
export async function waitForRuntime(store: Store): Promise<void> {
  await startRuntimeIfLazy();
  await waitForRuntimeRunning(store);
}

/**
 * Get this browser's edits to the host before a command that names cells.
 *
 * A run asks for the edits explicitly, so a synchronization that stalled
 * earlier is retried here rather than left to the footer's retry.
 */
export function syncEdits(model: DocumentModel): Promise<Protocol.Document> {
  return model.retry();
}

/**
 * Run `cellIds` through the host once this browser's edits have reached it.
 *
 * The cells read as queued at once. The host's run supersedes that as the
 * kernel plans them; a request that does not reach the host withdraws it
 * and reports why. A disabled cell is sent so the kernel sets it aside,
 * but is not shown queued, since nothing is planned for it.
 */
export async function runCells(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): Promise<void> {
  if (cellIds.length === 0) {
    return;
  }
  const model = store.get(activeDocumentModelAtom);
  if (model === null) {
    Logger.warn("No notebook is open to run cells in");
    return;
  }
  const document = store.get(model.documentAtom);
  submitCells(
    store,
    cellIds.filter(
      (cellId) => document?.cells.get(cellId)?.config.disabled !== true,
    ),
  );
  try {
    await waitForRuntime(store);
    const { notebook_id } = await syncEdits(model);
    // The request was for the notebook that was open when it was made.
    if (store.get(activeDocumentModelAtom) !== model) {
      return;
    }
    const backend = store.get(activeNotebookBackendAtom);
    if (backend === null) {
      throw new Error("The notebook is not connected");
    }
    const result = await backend
      .notebook(notebook_id)
      .run({ cells: cellIds.map((id) => ({ id })) });
    if (result.ok) {
      acceptRun(store, result.data);
      return;
    }
    withdrawCells(store, cellIds);
    // The connection is read-only for this action, which the UI shows.
    if (result.status === 403) {
      Logger.warn("Run refused, connection is read-only", result.problem);
      return;
    }
    Logger.error("The host refused the run", result.problem);
    toast({
      title: "Failed to run",
      description: result.problem.detail ?? result.problem.title,
      variant: "danger",
    });
  } catch (error) {
    withdrawCells(store, cellIds);
    Logger.error("Failed to run cells", error);
    toast({
      title: "Failed to run",
      description: prettyError(error),
      variant: "danger",
    });
  }
}
