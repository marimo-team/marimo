/* Copyright 2026 Marimo. All rights reserved. */

/** The active notebook's executions and runtime as the editor reads them. */

import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai";
import type { CellMessage } from "@/core/kernel/messages";
import type { Executions, Results } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { waitFor } from "@/core/state/jotai";
import {
  anyRunning,
  type CellExecutionInputs,
  latestExecutionId,
  queuedOrRunningCount,
} from "./select";

type Store = ReturnType<typeof createStore>;

const NO_EXECUTIONS: Executions = {
  runs: new Map(),
  executions: new Map(),
  latest: new Map(),
};
const NO_RESULTS: Results = new Map();

/**
 * Cells a run was requested for, with the execution each had at the time.
 *
 * The host shows a queued execution once the kernel plans the run. Until
 * then the cell reads as queued from this record. The host's newer
 * execution supersedes it; a rejected request, a cell the kernel will not
 * run, or the cell leaving the document withdraws it. Written only by
 * `submitCells`, `withdrawCells`, and `observeCellMessage`.
 */
const submissionsAtom = atom<
  ReadonlyMap<Protocol.CellId, Protocol.ExecutionId | null>
>(new Map<Protocol.CellId, Protocol.ExecutionId | null>());

/**
 * Cells the kernel reports as blocked by a disabled ancestor. Written only
 * by `observeCellMessage`.
 *
 * TODO(MO-8403): Derive this from the document and the analysis stream
 * once the editor reads dependencies from the host.
 */
const blockedCellsAtom = atom<ReadonlySet<Protocol.CellId>>(
  new Set<Protocol.CellId>(),
);

/** What every cell's view derives from. Pair with `cellExecutionView`. */
export const cellExecutionInputsAtom = atom((get): CellExecutionInputs => {
  const replica = get(activeNotebookReplicaAtom);
  return {
    executions: replica === null ? NO_EXECUTIONS : get(replica.executionsAtom),
    results: replica === null ? NO_RESULTS : get(replica.resultsAtom),
    submissions: get(submissionsAtom),
    blocked: get(blockedCellsAtom),
  };
});

/** The runtime's status, null while the notebook has none or the stream is not ready. */
export const runtimeStatusAtom = atom((get) => {
  const replica = get(activeNotebookReplicaAtom);
  return replica === null ? null : (get(replica.runtimeAtom)?.status ?? null);
});

export const notebookIsRunningAtom = atom((get) =>
  anyRunning(get(cellExecutionInputsAtom).executions),
);

export const notebookQueuedOrRunningCountAtom = atom((get) =>
  queuedOrRunningCount(get(cellExecutionInputsAtom)),
);

/** Resolve once the host reports the runtime running. */
export async function waitForRuntimeRunning(): Promise<void> {
  await waitFor(runtimeStatusAtom, (status) => status === "running");
}

/**
 * Record a run request for `cellIds` so they read as queued at once.
 *
 * Cells blocked by a disabled ancestor stay blocked: the kernel will not
 * queue them.
 */
export function submitCells(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): void {
  const inputs = store.get(cellExecutionInputsAtom);
  const next = new Map(store.get(submissionsAtom));
  for (const cellId of cellIds) {
    if (!inputs.blocked.has(cellId)) {
      next.set(cellId, latestExecutionId(inputs, cellId));
    }
  }
  store.set(submissionsAtom, next);
}

/** Forget a run request the host rejected. */
export function withdrawCells(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): void {
  const next = new Map(store.get(submissionsAtom));
  for (const cellId of cellIds) {
    next.delete(cellId);
  }
  store.set(submissionsAtom, next);
}

function setCellBlocked(
  store: Store,
  cellId: Protocol.CellId,
  blocked: boolean,
): void {
  const current = store.get(blockedCellsAtom);
  if (current.has(cellId) === blocked) {
    return;
  }
  const next = new Set(current);
  if (blocked) {
    next.add(cellId);
  } else {
    next.delete(cellId);
  }
  store.set(blockedCellsAtom, next);
}

/**
 * Keep the blocked set and the submissions in step with a cell-op.
 *
 * A status names whether the cell is blocked. A blocked cell and one whose
 * output is an error will not run, so a submission that never became an
 * execution is withdrawn, as it was when the editor set status itself.
 */
export function observeCellMessage(store: Store, message: CellMessage): void {
  const cellId = message.cell_id;
  const blocked = message.status === "disabled-transitively";
  if (message.status != null) {
    setCellBlocked(store, cellId, blocked);
  }
  if (blocked || message.output?.mimetype === "application/vnd.marimo+error") {
    withdrawCells(store, [cellId]);
  }
}
