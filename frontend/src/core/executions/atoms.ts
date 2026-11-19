/* Copyright 2026 Marimo. All rights reserved. */

/** The active notebook's executions and runtime as the editor reads them. */

import type * as Protocol from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import { atom, type createStore } from "jotai";
import { atomFamily, selectAtom } from "jotai/utils";
import type { CellId } from "@/core/cells/ids";
import type { Outline } from "@/core/cells/outline";
import { parseOutline } from "@/core/dom/outline";
import {
  ConnectionState,
  type Executions,
  type NotebookReplica,
  type Results,
} from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";
import { type CellFreshnessInputs, freshnessOf } from "./freshness";
import {
  type CellOutput,
  type CellOutputInputs,
  type ClearedOutput,
  cellOutputsView,
  shownExecution,
} from "./output";
import {
  anyRunning,
  type CellExecutionInputs,
  queuedOrRunningCount,
} from "./select";

type Store = ReturnType<typeof createStore>;

const NO_EXECUTIONS: Executions = {
  runs: new Map(),
  executions: new Map(),
  latest: new Map(),
  results: new Map(),
  scratch: null,
};
const NO_RESULTS: Results = new Map();
const NO_CELLS: ReadonlyMap<Protocol.CellId, Protocol.Cell> = new Map();
const NO_REQUESTS: ReadonlySet<RunRequest> = new Set();
const NO_REQUESTED: ReadonlySet<Protocol.CellId> = new Set();
const NO_BLOCKED: ReadonlySet<Protocol.CellId> = new Set();
const NO_CLEARED: ReadonlyMap<Protocol.CellId, ClearedOutput> = new Map();

/** The notebook a replica is showing, which the editor's marks belong to. */
interface ShownNotebook {
  readonly replica: NotebookReplica;
  readonly id: Protocol.NotebookId;
  readonly generation: number;
}

type Marks<T> = {
  readonly notebook: ShownNotebook;
  readonly value: T;
} | null;

/**
 * A run this browser has asked the host for.
 *
 * The host answers some time after the request is made, and by then the
 * notebook may have been replaced or the same cells asked for again. So
 * the functions that handle the answer are given the request back, and
 * they act only on it, in the notebook it was made in.
 */
export interface RunRequest {
  readonly notebook: ShownNotebook;
  readonly cells: readonly Protocol.CellId[];
}

/**
 * Requests whose run has not appeared on the stream yet.
 *
 * They let a requested cell read as queued right away. Once the host
 * accepts the run, the stream shows it with the same cells named on it,
 * and the request is no longer needed. A request the host refuses, or
 * that the browser gives up on, is withdrawn instead.
 */
const requestsAtom = atom<Marks<ReadonlySet<RunRequest>>>(null);

/**
 * Cells the kernel reports as blocked by a disabled ancestor. Written only
 * by the editor session.
 *
 * TODO(MO-8463): Derive from the document and the analysis stream.
 */
const blockedCellsAtom = atom<Marks<ReadonlySet<Protocol.CellId>>>(null);

function sameNotebook(
  marked: ShownNotebook,
  shown: ShownNotebook | null,
): boolean {
  return (
    shown !== null &&
    marked.replica === shown.replica &&
    marked.id === shown.id &&
    marked.generation === shown.generation
  );
}

function current<T>(marks: Marks<T>, shown: ShownNotebook | null, empty: T): T {
  return marks !== null && sameNotebook(marks.notebook, shown)
    ? marks.value
    : empty;
}

const shownNotebookAtom = atom((get): ShownNotebook | null => {
  const replica = get(activeNotebookReplicaAtom);
  const notebook = replica === null ? null : get(replica.notebookAtom);
  return replica === null || notebook === null
    ? null
    : { replica, id: notebook.id, generation: get(replica.generationAtom) };
});

/** Whether the request still belongs to the current stream. */
export function isCurrent(store: Store, request: RunRequest): boolean {
  return sameNotebook(request.notebook, store.get(shownNotebookAtom));
}

/** Cells named by pending requests made in the notebook now shown. */
const requestedCellsAtom = atom((get) => {
  const requests = current(
    get(requestsAtom),
    get(shownNotebookAtom),
    NO_REQUESTS,
  );
  return requests.size === 0
    ? NO_REQUESTED
    : new Set([...requests].flatMap((request) => request.cells));
});

/** What every cell's view derives from. Pair with `cellExecutionView`. */
export const cellExecutionInputsAtom = atom((get): CellExecutionInputs => {
  const replica = get(activeNotebookReplicaAtom);
  const document = replica === null ? null : get(replica.shownDocumentAtom);
  return {
    executions: replica === null ? NO_EXECUTIONS : get(replica.executionsAtom),
    results: replica === null ? NO_RESULTS : get(replica.resultsAtom),
    cells: document?.cells ?? NO_CELLS,
    requested: get(requestedCellsAtom),
    blocked: current(get(blockedCellsAtom), get(shownNotebookAtom), NO_BLOCKED),
    runtimeId: replica === null ? null : (get(replica.runtimeAtom)?.id ?? null),
  };
});

const cellFreshnessInputsAtom = atom((get): CellFreshnessInputs => {
  const replica = get(activeNotebookReplicaAtom);
  const document = replica === null ? null : get(replica.shownDocumentAtom);
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

/** What each cell showed when this browser cleared it. */
const clearedOutputsAtom =
  atom<Marks<ReadonlyMap<Protocol.CellId, ClearedOutput>>>(null);

const displayedNotebookAtom = atom((get): ShownNotebook | null => {
  const replica = get(activeNotebookReplicaAtom);
  const document = replica === null ? null : get(replica.shownDocumentAtom);
  return replica === null || document === null
    ? null
    : {
        replica,
        id: document.revision.notebook_id,
        generation: get(replica.generationAtom),
      };
});

/** What every cell's output derives from. Pair with `cellOutputView`. */
export const cellOutputInputsAtom = atom((get): CellOutputInputs => {
  const replica = get(activeNotebookReplicaAtom);
  return {
    executions: replica === null ? NO_EXECUTIONS : get(replica.executionsAtom),
    results: replica === null ? NO_RESULTS : get(replica.resultsAtom),
    cleared: current(
      get(clearedOutputsAtom),
      get(displayedNotebookAtom),
      NO_CLEARED,
    ),
    cells:
      replica === null
        ? NO_CELLS
        : (get(replica.documentAtom)?.cells ?? NO_CELLS),
  };
});

/** What every cell shows, by cell id. Pair with `cellOutputAtom` for one cell. */
export const cellOutputsAtom = atom((get) =>
  cellOutputsView(get(cellOutputInputsAtom)),
);

/**
 * One cell's output, compared by value so its readers are left alone by
 * other cells' runs. Released with the cell by `releaseCellOutputAtoms`.
 */
export const cellOutputAtom = atomFamily((cellId: CellId) =>
  selectAtom(
    cellOutputsAtom,
    (outputs): CellOutput | null => outputs.get(cellId) ?? null,
    dequal,
  ),
);

/** The headings in a cell's output, for the table of contents and folding. */
export const cellOutlineAtom = atomFamily((cellId: CellId) =>
  atom((get): Outline | null => parseOutline(get(cellOutputAtom(cellId)))),
);

/** Drop the cached atoms of a cell that left the document. */
export function releaseCellOutputAtoms(cellId: CellId): void {
  cellOutputAtom.remove(cellId);
  cellOutlineAtom.remove(cellId);
}

/** Hide what `cellIds` show now, until each shows something new. */
export function clearCellOutputs(
  store: Pick<Store, "get" | "set">,
  cellIds: readonly Protocol.CellId[],
): void {
  const inputs = store.get(cellOutputInputsAtom);
  const next = new Map(inputs.cleared);
  for (const cellId of cellIds) {
    const shown = shownExecution(inputs, cellId);
    if (shown?.record.outcome != null) {
      next.set(cellId, {
        execution: shown.record.id,
        version: shown.outputVersion,
      });
    }
  }
  const notebook = store.get(displayedNotebookAtom);
  store.set(
    clearedOutputsAtom,
    notebook === null ? null : { notebook, value: next },
  );
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

type RuntimeReadiness = "running" | "waiting" | { refused: string };

/**
 * Whether a run can go to the host now, should wait, or has nothing to wait for.
 *
 * A runtime that is starting, or a stream that has not reported yet, will
 * settle one way or the other. A failed or absent runtime, or a connection
 * that has closed, will not, so a run waiting on it is refused instead.
 */
const runtimeReadinessAtom = atom((get): RuntimeReadiness => {
  const replica = get(activeNotebookReplicaAtom);
  if (replica === null) {
    return { refused: "No notebook is connected" };
  }
  if (get(replica.connectionAtom).state === ConnectionState.CLOSED) {
    return { refused: "The notebook is disconnected" };
  }
  // Until the stream's snapshot is complete there is no notebook to speak
  // of, and nothing it reports about the runtime counts yet.
  if (get(replica.notebookAtom) === null) {
    return "waiting";
  }
  const runtime = get(replica.runtimeAtom);
  if (runtime === null) {
    return { refused: "The notebook has no runtime" };
  }
  switch (runtime.status) {
    case "running":
      return "running";
    case "failed":
      return { refused: runtime.message ?? "The runtime failed" };
    default:
      return "waiting";
  }
});

/** Resolve once the host reports the runtime running; reject once it cannot. */
export function waitForRuntimeRunning(store: Store): Promise<void> {
  return new Promise((resolve, reject) => {
    const unsubscribe = store.sub(runtimeReadinessAtom, check);
    function check() {
      const readiness = store.get(runtimeReadinessAtom);
      if (readiness === "waiting") {
        return;
      }
      unsubscribe();
      if (readiness === "running") {
        resolve();
      } else {
        reject(new Error(readiness.refused));
      }
    }
    check();
  });
}

/**
 * Record that this browser is asking the host to run `cellIds`, so that
 * they read as queued before the host has answered.
 *
 * A disabled cell, or one the kernel reports as blocked, may be among them
 * so the kernel can set it aside, but the views do not show it as queued.
 * Returns null while no notebook is shown, since there is nothing to
 * record the request against.
 */
export function requestRun(
  store: Store,
  cellIds: readonly Protocol.CellId[],
): RunRequest | null {
  const notebook = store.get(shownNotebookAtom);
  if (notebook === null) {
    return null;
  }
  const request: RunRequest = { notebook, cells: [...cellIds] };
  const kept = current(store.get(requestsAtom), notebook, NO_REQUESTS);
  store.set(requestsAtom, { notebook, value: new Set(kept).add(request) });
  return request;
}

/** Forget a request the host refused or the browser gave up on. */
export function withdrawRequest(store: Store, request: RunRequest): void {
  const marks = store.get(requestsAtom);
  if (marks === null || !marks.value.has(request)) {
    return;
  }
  const value = new Set(marks.value);
  value.delete(request);
  store.set(requestsAtom, { notebook: marks.notebook, value });
}

/**
 * Keep a request until the run the host accepted for it appears on the
 * stream, which can happen after the response has arrived. From then on
 * the run itself says which cells are queued. If the notebook is no
 * longer shown by then, the request is simply dropped.
 */
export function acceptRun(
  store: Store,
  request: RunRequest,
  run: Protocol.Run,
): void {
  const waitingAtom = atom(
    (get) =>
      sameNotebook(request.notebook, get(shownNotebookAtom)) &&
      !get(request.notebook.replica.executionsAtom).runs.has(run.id),
  );
  const unsubscribe = store.sub(waitingAtom, check);
  function check() {
    if (store.get(waitingAtom)) {
      return;
    }
    unsubscribe();
    withdrawRequest(store, request);
  }
  check();
}

export function setCellBlocked(
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
  const notebook = store.get(shownNotebookAtom);
  if (notebook !== null) {
    store.set(blockedCellsAtom, { notebook, value: next });
  }
}
