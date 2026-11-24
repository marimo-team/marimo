/* Copyright 2026 Marimo. All rights reserved. */

/**
 * A notebook session without React, shaped like the 521-cell notebook in
 * `large-notebook-state.bench.ts`: a setup cell, then hidden markdown cells
 * alternating with 1 KB code cells that read only the setup cell.
 */

import {
  createNotebookReducer,
  NotebookEvents,
  type NotebookStreamEvent,
  type NotebookTransport,
} from "@marimo-team/client";
import type * as Protocol from "@marimo-team/client/protocol";
import { dequal } from "dequal";
import { type Atom, atom, createStore } from "jotai";
import { selectAtom } from "jotai/utils";
import { expect } from "vitest";
import {
  cellDataAtom,
  cellErrorCount,
  cellHandleAtom,
  cellIdsAtom,
  cellRuntimeAtom,
  notebookAtom,
  notebookOutline,
  notebookReducer,
  runReasonAtom,
} from "@/core/cells/cells";
import { followDocument } from "@/core/cells/document";
import type { CellId } from "@/core/cells/ids";
import { layoutAtom } from "@/core/cells/layout";
import { exportedForTesting as runs } from "@/core/cells/runs";
import {
  cellExecutionInputsAtom,
  cellExecutionView,
  cellFreshnessAtom,
  cellOutlineAtom,
  cellOutputAtom,
  cellOutputsAtom,
  notebookIsRunningAtom,
  notebookQueuedOrRunningCountAtom,
} from "@/core/executions";
import {
  createDocumentModel,
  type DocumentModel,
} from "@/core/notebook/document";
import { selectCellField } from "@/core/notebook/document/select";
import {
  ConnectionState,
  createNotebookReplica,
  EDITOR_EVENT_KINDS,
  type NotebookBackend,
  type NotebookReplica,
} from "@/core/notebook/replica";
import { analysis } from "@/core/notebook/replica/resources/analysis";
import { attachments } from "@/core/notebook/replica/resources/attachments";
import { document } from "@/core/notebook/replica/resources/document";
import { executions } from "@/core/notebook/replica/resources/executions";
import { runtime } from "@/core/notebook/replica/resources/runtime";
import { needsSaveAtom } from "@/core/saving/state";
import {
  activeDocumentModelAtom,
  activeNotebookReplicaAtom,
} from "@/core/session/active-notebook";

export type Store = ReturnType<typeof createStore>;
export type Event = Protocol.NotebookStreamEvent;
type EditorEvent = NotebookStreamEvent<(typeof EDITOR_EVENT_KINDS)[number]>;

const NOTEBOOK = "nb-bench";
const RUNTIME = "rt-bench";
const T0 = "2026-11-24T20:04:56.944578Z";
const T1 = "2026-11-24T20:04:56.997879Z";
const SETUP_DEFS = ["Path", "json", "math", "mo"];
const CONFIG = {
  column: null,
  disabled: false,
  expand_output: false,
  hide_code: false,
};

// About 1 KB, like the median code cell of the slow notebook.
export const CODE = Array.from(
  { length: 32 },
  (_, i) => `_value_${i} = math.sqrt(${i}) + len(json.dumps({"k": ${i}}))`,
).join("\n");
const markdown = (i: number) =>
  `mo.md(r"""\n## R${i}. \`feature_${i}\` keeps its contract (#${10_000 + i})\n""")`;
const rendered = (i: number) =>
  `<span class="markdown prose dark:prose-invert contents"><h2 id="r${i}">R${i}. <code>feature_${i}</code> keeps its contract (#${10_000 + i})</h2></span>`;

const isMarkdown = (i: number) => i % 2 === 1;
export const cellIdOf = (i: number) => (i === 0 ? "setup" : `c${i}`);
export const executionIdOf = (run: number, i: number) => `e${run}-${i}`;

export function cellRecord(
  i: number,
  code?: string,
  version = 1,
): Protocol.Cell {
  const source =
    code ??
    (i === 0 ? "import json, math" : isMarkdown(i) ? markdown(i) : CODE);
  return {
    id: cellIdOf(i),
    notebook_id: NOTEBOOK,
    name: i === 0 ? "setup" : "_",
    code: source,
    code_fingerprint: `py-ast-v1:3.13:${i}-${version}`,
    config: { ...CONFIG, hide_code: isMarkdown(i) },
    etag: `cell-${i}-${version}`,
    version,
  };
}

export function documentEvent(n: number, version = 1): Event {
  return {
    event: "document",
    data: {
      document: {
        notebook_id: NOTEBOOK,
        app_config: { width: "medium" },
        app_config_etag: "config",
        etag: `document-${version}`,
        saved_etag: "document-1",
        order: Array.from({ length: n }, (_, i) => cellIdOf(i)),
        order_etag: "order",
        version,
      },
    },
  };
}

/** The star graph of the slow notebook: every cell reads only the setup cell. */
export function analysisEvent(n: number, version = 1): Event {
  const cells: Protocol.Analysis["cells"] = {};
  for (let i = 0; i < n; i++) {
    cells[cellIdOf(i)] = {
      defs: i === 0 ? SETUP_DEFS : [],
      refs: i === 0 ? [] : isMarkdown(i) ? ["mo"] : ["json", "math"],
      parents: i === 0 ? [] : ["setup"],
      diagnostics: [],
    };
  }
  return {
    event: "analysis",
    data: {
      analysis: {
        notebook_id: NOTEBOOK,
        document_etag: `document-${version}`,
        cells,
      },
    },
  };
}

export function snapshot(n: number): Event[] {
  return [
    {
      event: "notebook",
      data: {
        notebook: {
          id: NOTEBOOK,
          project_id: "project",
          path: "bench.py",
          name: "bench",
          operations: ["notebook.edit", "runtime.run"],
          modified_at: T0,
        },
      },
    },
    ...Array.from({ length: n }, (_, i): Event => ({
      event: "cell",
      data: { cell: cellRecord(i) },
    })),
    documentEvent(n),
    {
      event: "runtime",
      data: {
        runtime: {
          id: RUNTIME,
          notebook_id: NOTEBOOK,
          marimo_version: "0.0.0",
          created_at: T0,
          state: { status: "ready" },
        },
      },
    },
    { event: "ready", data: {}, id: "cursor-0" },
    analysisEvent(n),
  ];
}

export function execution(
  run: number,
  i: number,
  state: Protocol.ExecutionState,
): Event {
  return {
    event: "execution",
    id: `cursor-${run}-${i}-${state.status}`,
    data: {
      time: T1,
      execution: {
        id: executionIdOf(run, i),
        run_id: `run-${run}`,
        runtime_id: RUNTIME,
        caused_by_id: null,
        cell_id: cellIdOf(i),
        code_fingerprint: `py-ast-v1:3.13:${i}-1`,
        created_at: T0,
        state,
      },
    },
  };
}

/** One cell running to completion: the events the kernel sends for it. */
export function lifecycle(run: number, i: number, setupRun = run): Event[] {
  const id = executionIdOf(run, i);
  // The setup execution whose variables the cell read.
  const setup = executionIdOf(setupRun, 0);
  const reads = i === 0 ? [] : isMarkdown(i) ? ["mo"] : ["json", "math"];
  return [
    execution(run, i, { status: "running", started_at: T0 }),
    {
      event: "output",
      data: {
        time: T1,
        output: {
          id: `${id}:output`,
          execution_id: id,
          media: isMarkdown(i)
            ? { mimetype: "text/markdown", data: rendered(i) }
            : null,
        },
      },
    },
    ...(i === 0 ? SETUP_DEFS : []).map((name): Event => ({
      event: "variable",
      data: {
        time: T1,
        variable: {
          id: `${id}-variable-${name}`,
          execution_id: id,
          name,
          type: null,
          preview: null,
          revision: { execution_id: id, update: 0 },
        },
      },
    })),
    execution(run, i, {
      status: "completed",
      started_at: T0,
      completed_at: T1,
      outcome: { kind: "succeeded" },
      depends_on: Object.fromEntries(
        reads.map((name) => [name, { execution_id: setup, update: 0 }]),
      ),
    }),
  ];
}

/** A run of every cell: all are queued, then each runs in turn. */
export function runAll(n: number, run: number): Event[] {
  const runEvent = (state: Protocol.RunState): Event => ({
    event: "run",
    data: {
      time: T1,
      run: {
        id: `run-${run}`,
        notebook_id: NOTEBOOK,
        runtime_id: RUNTIME,
        created_at: T0,
        origin: {
          kind: "cells",
          cell_ids: Array.from({ length: n }, (_, i) => cellIdOf(i)),
        },
        state,
      },
    },
  });
  const indices = Array.from({ length: n }, (_, i) => i);
  return [
    { event: "run.removed", data: { id: `run-${run - 1}` } },
    runEvent({ status: "queued" }),
    ...indices.flatMap((i): Event[] => [
      // The host keeps one execution per cell on the stream.
      { event: "execution.removed", data: { id: executionIdOf(run - 1, i) } },
      execution(run, i, { status: "queued" }),
    ]),
    runEvent({ status: "running", started_at: T0 }),
    ...indices.flatMap((i) => lifecycle(run, i)),
    runEvent({
      status: "completed",
      started_at: T0,
      completed_at: T1,
      outcome: { kind: "succeeded" },
    }),
  ];
}

/** The atoms one mounted cell subscribes to, and the notebook chrome around them. */
function mount(store: Store, model: DocumentModel, ids: readonly CellId[]) {
  const atoms: Array<Atom<unknown>> = [
    cellIdsAtom,
    layoutAtom,
    runReasonAtom,
    cellErrorCount,
    notebookOutline,
    notebookIsRunningAtom,
    notebookQueuedOrRunningCountAtom,
    needsSaveAtom,
    cellOutputsAtom,
  ];
  for (const id of ids) {
    const view = () =>
      selectAtom(
        cellExecutionInputsAtom,
        (inputs) => cellExecutionView(inputs, id),
        dequal,
      );
    atoms.push(
      cellHandleAtom(id),
      cellDataAtom(id),
      cellRuntimeAtom(id),
      cellOutputAtom(id),
      cellOutlineAtom(id),
      // The cell and its context menu each read the execution view.
      view(),
      view(),
      selectAtom(cellFreshnessAtom, (freshness) => freshness(id), dequal),
      selectCellField(model.documentAtom, id, "code"),
    );
  }
  const unsubscribes = atoms.map((value) => store.sub(value, () => undefined));
  return () => unsubscribes.forEach((unsubscribe) => unsubscribe());
}

export const reducer = createNotebookReducer({
  document,
  analysis,
  attachments,
  runtime,
  executions,
});
type Stream = typeof reducer.initial;

/**
 * The replica's atoms over a stream this benchmark sets, so that several
 * events can reach the store as one update.
 */
function batchedReplica(streamAtom: Atom<Stream>): NotebookReplica {
  const documentAtom = atom(
    (get) => get(streamAtom).resources.document.current,
  );
  const executionsAtom = atom((get) => get(streamAtom).resources.executions);
  return {
    connectionAtom: atom({ state: ConnectionState.OPEN }),
    generationAtom: atom(1),
    notebookAtom: atom((get) => get(streamAtom).notebook),
    documentAtom,
    shownDocumentAtom: documentAtom,
    analysisAtom: atom((get) => {
      const { analysis, document } = get(streamAtom).resources;
      return analysis === null || document.current === null
        ? null
        : {
            freshness:
              analysis.document_etag === document.current.revision.etag
                ? ("current" as const)
                : ("stale" as const),
            analysis,
            document: document.current,
          };
    }),
    backendAtom: atom<NotebookBackend | null>(null),
    attachmentsAtom: atom((get) => get(streamAtom).resources.attachments),
    runtimeAtom: atom((get) => get(streamAtom).resources.runtime),
    executionsAtom,
    resultsAtom: atom((get) => get(executionsAtom).results),
    connect: () => () => undefined,
    reconnect: () => Promise.resolve(),
  };
}

export interface Harness {
  store: Store;
  model: DocumentModel;
  /** Deliver events as the transport would, validated by the protocol. */
  send(events: readonly Event[]): void;
  stop(): void;
}

/**
 * A notebook session without React: the stream, the document model, the
 * notebook reducer that follows it, and the subscriptions of mounted cells.
 *
 * `per-event` is the editor's replica, which updates the store on every
 * event. `batched` reduces a delivery's events first and updates once.
 */
export async function createHarness(
  n: number,
  mode: "per-event" | "batched",
  {
    mounted = true,
    backend = null,
  }: {
    /** Subscribe as a mounted editor would. */
    mounted?: boolean;
    /** Where edits are sent. Without one, edits stay local and no timer starts. */
    backend?: NotebookBackend | null;
  } = {},
): Promise<Harness> {
  const store = createStore();
  const lifetime = new AbortController();
  const dispatch = (action: Parameters<typeof notebookReducer>[1]) =>
    store.set(notebookAtom, (state) => notebookReducer(state, action));
  const runsAtom = atom(runs.initialState());
  const onExecution = (record: Protocol.Execution, changed: boolean) => {
    if (!changed) {
      return;
    }
    if (record.state.status === "running") {
      dispatch({
        type: "startCellConsole",
        payload: { cellId: record.cell_id as CellId },
      });
    }
    store.set(runsAtom, (state) =>
      runs.reducer(state, {
        type: "addExecution",
        payload: { record, code: undefined, receivedAt: 0 },
      }),
    );
  };

  let message: (message: unknown) => void = () => undefined;
  const transport: NotebookTransport = ({ signal }, handlers) =>
    new Promise((resolve) => {
      handlers.open();
      message = handlers.message;
      signal.addEventListener("abort", () => resolve(), { once: true });
    });

  let replica: NotebookReplica;
  let flush = () => undefined;
  if (mode === "per-event") {
    replica = createNotebookReplica(store);
    const disconnect = replica.connect(
      { transport, notebook: () => expect.unreachable() },
      { onNotification: () => undefined, onExecution },
    );
    lifetime.signal.addEventListener("abort", disconnect, { once: true });
  } else {
    const streamAtom = atom(reducer.initial);
    replica = batchedReplica(streamAtom);
    const queue: EditorEvent[] = [];
    new NotebookEvents(transport, {
      kinds: EDITOR_EVENT_KINDS,
      signal: lifetime.signal,
    }).subscribe((event) => queue.push(event));
    flush = () => {
      let stream = store.get(streamAtom);
      const started = new Set<CellId>();
      const changed: Protocol.Execution[] = [];
      for (const event of queue.splice(0)) {
        const previous =
          event.event === "execution"
            ? stream.resources.executions.executions.get(
                event.data.execution.id,
              )
            : undefined;
        stream = reducer.reduce(
          stream,
          event as Protocol.NotebookStreamEventOutput,
        );
        if (
          event.event === "execution" &&
          previous?.record.state.status !== event.data.execution.state.status
        ) {
          changed.push(event.data.execution);
          if (event.data.execution.state.status === "running") {
            started.add(event.data.execution.cell_id as CellId);
          }
        }
      }
      store.set(streamAtom, stream);
      // One copy of the runtime record for every console the batch started.
      store.set(notebookAtom, (state) => {
        const cellRuntime = { ...state.cellRuntime };
        for (const id of started) {
          cellRuntime[id] = { ...cellRuntime[id], embeddedConsole: [] };
        }
        return { ...state, cellRuntime };
      });
      store.set(runsAtom, (state) =>
        changed.reduce(
          (next, record) =>
            runs.reducer(next, {
              type: "addExecution",
              payload: { record, code: undefined, receivedAt: 0 },
            }),
          state,
        ),
      );
    };
  }
  // The stream starts in a microtask, and the transport opens in the next.
  await new Promise((resolve) => setTimeout(resolve, 0));

  store.set(activeNotebookReplicaAtom, replica);
  const model = createDocumentModel({
    store,
    documentAtom: replica.documentAtom,
    shownDocumentAtom: replica.shownDocumentAtom,
    backendAtom: atom(backend),
  });
  model.start({ signal: lifetime.signal });
  store.set(activeDocumentModelAtom, model);
  followDocument({
    store,
    model,
    reconcile: (payload) => dispatch({ type: "reconcileDocument", payload }),
    signal: lifetime.signal,
  });

  const send = (events: readonly Event[]) => {
    events.forEach((event) => message(event));
    flush();
  };
  send(snapshot(n));
  const ids = store.get(cellIdsAtom);
  expect(ids).toHaveLength(n);
  // The first run precedes the subscriptions, so that setup stays linear.
  send(runAll(n, 0));
  const unmount = mounted ? mount(store, model, ids) : () => undefined;
  expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(0);
  expect(store.get(cellOutputsAtom).size).toBe(Math.floor(n / 2));

  return {
    store,
    model,
    send,
    stop: () => {
      unmount();
      lifetime.abort();
    },
  };
}

/** The events as the stream delivers them, validated by the protocol. */
export async function validate(
  messages: readonly Event[],
): Promise<Protocol.NotebookStreamEventOutput[]> {
  const parsed: Protocol.NotebookStreamEventOutput[] = [];
  const transport: NotebookTransport = async (_attempt, handlers) =>
    messages.forEach((message) => handlers.message(message));
  new NotebookEvents(transport).subscribe((event) => parsed.push(event));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(parsed).toHaveLength(messages.length);
  return parsed;
}
