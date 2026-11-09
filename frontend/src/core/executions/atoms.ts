/* Copyright 2026 Marimo. All rights reserved. */

/** The active notebook's executions and runtime as the editor reads them. */

import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai";
import type { CellMessage } from "@/core/kernel/messages";
import type {
  Executions,
  NotebookReplica,
  Results,
} from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { waitFor } from "@/core/state/jotai";
import { type CellFreshnessInputs, freshnessOf } from "./freshness";
import type { CellOutputInputs } from "./output";
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
const NO_CELLS: ReadonlyMap<Protocol.CellId, Protocol.Cell> = new Map();
const NO_SUBMISSIONS: ReadonlyMap<
  Protocol.CellId,
  Protocol.ExecutionId | null
> = new Map();
const NO_BLOCKED: ReadonlySet<Protocol.CellId> = new Set();
const NO_CLEARED: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId> =
  new Map();

/**
 * What the editor marks about cells of one replica's notebook.
 *
 * The marks are keyed by cell id, which another notebook, or the same one
 * after a reconnect, reuses with different executions behind it. They
 * therefore count only for the replica and host notebook they belong to.
 */
type Marks<T> = {
  readonly notebook: {
    readonly replica: NotebookReplica;
    readonly id: Protocol.NotebookId;
  };
  readonly value: T;
} | null;

/**
 * Cells a run was requested for, with the execution each had at the time.
 *
 * The host shows a queued execution once the kernel plans the run. Until
 * then the cell reads as queued from this record. The host's newer
 * execution supersedes it; a rejected request, a cell the kernel will not
 * run, or the cell leaving the document withdraws it. Written only by
 * `submitCells`, `withdrawCells`, `acceptRun`, and `observeCellMessage`.
 */
const submissionsAtom =
  atom<Marks<ReadonlyMap<Protocol.CellId, Protocol.ExecutionId | null>>>(null);

/**
 * Cells the kernel reports as blocked by a disabled ancestor. Written only
 * by `observeCellMessage`.
 *
 * TODO(MO-8463): Derive from the document and the analysis stream.
 */
const blockedCellsAtom = atom<Marks<ReadonlySet<Protocol.CellId>>>(null);

function current<T>(
  marks: Marks<T>,
  replica: NotebookReplica | null,
  notebookId: Protocol.NotebookId | null,
  empty: T,
): T {
  return marks !== null &&
    marks.notebook.replica === replica &&
    marks.notebook.id === notebookId
    ? marks.value
    : empty;
}

function mark<T>(store: Store, value: T): Marks<T> {
  const replica = store.get(activeNotebookReplicaAtom);
  const notebook = replica === null ? null : store.get(replica.notebookAtom);
  return replica === null || notebook === null
    ? null
    : { notebook: { replica, id: notebook.id }, value };
}

/** What every cell's view derives from. Pair with `cellExecutionView`. */
export const cellExecutionInputsAtom = atom((get): CellExecutionInputs => {
  const replica = get(activeNotebookReplicaAtom);
  const notebookId =
    replica === null ? null : (get(replica.notebookAtom)?.id ?? null);
  return {
    executions: replica === null ? NO_EXECUTIONS : get(replica.executionsAtom),
    results: replica === null ? NO_RESULTS : get(replica.resultsAtom),
    submissions: current(
      get(submissionsAtom),
      replica,
      notebookId,
      NO_SUBMISSIONS,
    ),
    blocked: current(get(blockedCellsAtom), replica, notebookId, NO_BLOCKED),
  };
});

const cellFreshnessInputsAtom = atom((get): CellFreshnessInputs => {
  const replica = get(activeNotebookReplicaAtom);
  const document = replica === null ? null : get(replica.documentAtom);
  // Results can arrive before the confirmed document on a snapshot. Until
  // the document is ready there is nothing to compare them against.
  if (replica === null || document === null) {
    return { cells: NO_CELLS, executions: NO_EXECUTIONS, results: NO_RESULTS };
  }
  return {
    cells: document.cells,
    executions: get(replica.executionsAtom),
    results: get(replica.resultsAtom),
  };
});

/** Freshness by cell id, indexed once per change to its inputs. */
export const cellFreshnessAtom = atom((get) =>
  freshnessOf(get(cellFreshnessInputsAtom)),
);

/** Results this browser cleared, by execution id, until a newer one lands. */
const clearedOutputsAtom =
  atom<Marks<ReadonlyMap<Protocol.CellId, Protocol.ExecutionId>>>(null);

/** What every cell's output derives from. Pair with `cellOutputView`. */
export const cellOutputInputsAtom = atom((get): CellOutputInputs => {
  const replica = get(activeNotebookReplicaAtom);
  const notebookId =
    replica === null ? null : (get(replica.notebookAtom)?.id ?? null);
  return {
    executions: replica === null ? NO_EXECUTIONS : get(replica.executionsAtom),
    results: replica === null ? NO_RESULTS : get(replica.resultsAtom),
    cleared: current(get(clearedOutputsAtom), replica, notebookId, NO_CLEARED),
  };
});

/** Hide what `cellIds` show now, until each has a newer result. */
export function clearCellOutputs(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): void {
  const inputs = store.get(cellOutputInputsAtom);
  const next = new Map(inputs.cleared);
  for (const cellId of cellIds) {
    const result = inputs.results.get(cellId);
    if (result !== null && result !== undefined) {
      next.set(cellId, result.id);
    }
  }
  store.set(clearedOutputsAtom, mark(store, next));
}

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
 * queue them. A disabled cell is not queued either; the caller leaves it
 * out, since its configuration lives in the notebook state.
 */
export function submitCells(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): void {
  const inputs = store.get(cellExecutionInputsAtom);
  const next = new Map(inputs.submissions);
  for (const cellId of cellIds) {
    if (!inputs.blocked.has(cellId)) {
      next.set(cellId, latestExecutionId(inputs, cellId));
    }
  }
  setSubmissions(store, next);
}

function setSubmissions(
  store: Store,
  value: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId | null>,
): void {
  store.set(submissionsAtom, mark(store, value));
}

/** Forget a run request the host rejected. */
export function withdrawCells(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): void {
  const next = new Map(store.get(cellExecutionInputsAtom).submissions);
  for (const cellId of cellIds) {
    next.delete(cellId);
  }
  setSubmissions(store, next);
}

/**
 * Follow a run the host accepted for submitted cells.
 *
 * The run's executions supersede the submissions as the kernel plans them.
 * A cell the kernel never plans, as when the run is interrupted first or
 * the kernel drops the cell, gets none, so its submission is withdrawn once
 * the run completes or leaves the stream. A submission made since then is
 * another request and stays.
 */
export function acceptRun(store: Store, run: Protocol.Run): void {
  const replica = store.get(activeNotebookReplicaAtom);
  if (replica === null) {
    return;
  }
  const submissions = store.get(cellExecutionInputsAtom).submissions;
  const awaiting = new Map(
    run.cells.flatMap((cellId) =>
      submissions.has(cellId)
        ? [[cellId, submissions.get(cellId) ?? null] as const]
        : [],
    ),
  );
  if (awaiting.size > 0) {
    followRun(store, replica, run.id, awaiting);
  }
}

/** Withdraw what is left of `awaiting` once the run has ended. */
function followRun(
  store: Store,
  replica: NotebookReplica,
  runId: Protocol.RunId,
  awaiting: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId | null>,
): void {
  // The response can land before the stream shows the run, so an absent
  // run means removed only once it has been seen.
  let seen = false;
  const unsubscribe = store.sub(replica.executionsAtom, check);
  function check() {
    if (store.get(activeNotebookReplicaAtom) !== replica) {
      unsubscribe();
      return;
    }
    const current = store.get(replica.executionsAtom).runs.get(runId);
    if (current !== undefined && current.status !== "completed") {
      seen = true;
      return;
    }
    if (current === undefined && !seen) {
      return;
    }
    unsubscribe();
    const now = store.get(cellExecutionInputsAtom).submissions;
    withdrawCells(
      store,
      [...awaiting].flatMap(([cellId, executionId]) =>
        now.has(cellId) && now.get(cellId) === executionId ? [cellId] : [],
      ),
    );
  }
  check();
}

function setCellBlocked(
  store: Store,
  cellId: Protocol.CellId,
  blocked: boolean,
): void {
  const known = store.get(cellExecutionInputsAtom).blocked;
  if (known.has(cellId) === blocked) {
    return;
  }
  const next = new Set(known);
  if (blocked) {
    next.add(cellId);
  } else {
    next.delete(cellId);
  }
  store.set(blockedCellsAtom, mark(store, next));
}

/**
 * Keep the blocked set and the submissions in step with a cell-op.
 *
 * A status names whether the cell is blocked. A blocked cell and one whose
 * output is an error will not run, so a submission that never became an
 * execution is withdrawn, as it was when the editor set status itself.
 *
 * TODO(MO-8407): Delete with the cell-op case. The blocked read goes with
 * MO-8463, the error read with MO-8346.
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
