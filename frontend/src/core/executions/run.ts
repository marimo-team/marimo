/* Copyright 2026 Marimo. All rights reserved. */

/** Submit cell runs to the host. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { createStore } from "jotai";
import type { DocumentModel } from "@/core/notebook/document";
import { toast } from "@/components/ui/use-toast";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import {
  acceptRun,
  isCurrent,
  requestRun,
  waitForRuntimeRunning,
  withdrawRequest,
} from "./atoms";

type Store = ReturnType<typeof createStore>;

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
 * The cells read as queued right away. When the host accepts the run, the
 * stream shows it with the same cells named on it and takes over from the
 * request. A request that never reaches the host is withdrawn, and the
 * user is told why. The request belongs to the notebook it was made in, so
 * if another notebook is shown by the time the edits have synced, it is
 * dropped rather than sent there.
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
  // The stream may have no notebook for a moment, as during a reconnect.
  // The request is then recorded once the runtime, and with it the
  // notebook, has been seen.
  let request = requestRun(store, cellIds);
  try {
    await waitForRuntimeRunning(store);
    request ??= requestRun(store, cellIds);
    if (request === null) {
      throw new Error("No notebook is shown");
    }
    const { notebook_id } = await syncEdits(model);
    if (
      store.get(activeDocumentModelAtom) !== model ||
      !isCurrent(store, request) ||
      notebook_id !== request.notebook.id
    ) {
      withdrawRequest(store, request);
      return;
    }
    const backend = store.get(request.notebook.replica.backendAtom);
    if (backend === null) {
      throw new Error("The notebook is not connected");
    }
    const result = await backend
      .notebook(notebook_id)
      .run({ cells: cellIds.map((id) => ({ id })) });
    if (result.ok) {
      acceptRun(store, request, result.data);
      return;
    }
    withdrawRequest(store, request);
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
    if (request !== null) {
      withdrawRequest(store, request);
    }
    Logger.error("Failed to run cells", error);
    toast({
      title: "Failed to run",
      description: prettyError(error),
      variant: "danger",
    });
  }
}
