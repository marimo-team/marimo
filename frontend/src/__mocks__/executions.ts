/* Copyright 2026 Marimo. All rights reserved. */

/** Executions as the host would report them, for tests that read cell status. */

import { cellId, runId } from "@/__tests__/branded";
import type * as Protocol from "@marimo-team/client/protocol";
import { atom, type createStore } from "jotai";
import type { CellExecutionInputs } from "@/core/executions";
import {
  ConnectionState,
  type ConnectionStatus,
  type Document,
  type Execution,
  type Item,
  type Executions,
  type NotebookBackend,
  type NotebookReplica,
  type Results,
  type Result,
} from "@/core/notebook/replica";
import { shown } from "@/core/notebook/replica";
import { activeNotebookReplicaAtom } from "@/core/session/active-notebook";

type Store = ReturnType<typeof createStore>;

const CONFIG: Protocol.CellConfig = {
  column: null,
  disabled: false,
  hide_code: false,
  expand_output: false,
};
const T0 = "2026-10-01T09:20:11Z";
const T1 = "2026-10-01T09:20:12.500Z";

let sequence = 0;

const READY: Protocol.RuntimeState = { status: "ready" };
const SUCCEEDED: Protocol.ExecutionOutcomeOutput = { kind: "succeeded" };

/** An execution, or the output it set, as the stream delivers them. */
type ExecutionFixture = Protocol.ExecutionOutput & {
  items?: readonly Item[];
  bindings?: readonly Pick<Protocol.Variable, "name" | "type" | "preview">[];
};
type Entry = ExecutionFixture | Protocol.Output;
export type ExecutionEntries = ReadonlyArray<Entry | readonly Entry[]>;

function split(entries: ExecutionEntries) {
  const records: ExecutionFixture[] = [];
  const outputs = new Map<Protocol.ExecutionId, Protocol.Output>();
  for (const entry of entries.flat()) {
    if ("execution_id" in entry) {
      outputs.set(entry.execution_id, entry);
    } else {
      records.push(entry);
    }
  }
  return { records, outputs };
}

function execution(
  cid: string | null,
  state: Protocol.ExecutionStateOutput,
): Protocol.ExecutionOutput {
  sequence += 1;
  return {
    id: `e${sequence}`,
    run_id: runId("run-1"),
    runtime_id: "r1",
    caused_by_id: null,
    cell_id: cid === null ? null : cellId(cid),
    code_fingerprint: "0f71456db2ea83f4",
    created_at: T0,
    state,
  };
}

function completed(
  cellId: string | null,
  outcome: Protocol.ExecutionOutcomeOutput = SUCCEEDED,
): Protocol.ExecutionOutput {
  return execution(cellId, {
    status: "completed",
    started_at: T0,
    completed_at: T1,
    outcome,
    depends_on: {},
  });
}

function output(
  execution: Protocol.Execution,
  media: Protocol.Media | null,
): Protocol.Output {
  return { id: `${execution.id}:output`, execution_id: execution.id, media };
}

function mirror(entries: ExecutionEntries): Executions {
  const { records, outputs } = split(entries);
  const executions = new Map<Protocol.ExecutionId, Execution>();
  const latest = new Map<Protocol.CellId, Protocol.ExecutionId>();
  const variables = new Map<
    Protocol.CellId,
    Map<Protocol.ItemId, Protocol.Variable>
  >();
  for (const { items = [], bindings = [], ...record } of records) {
    if (record.cell_id !== null) {
      // The host retains one execution per cell on the stream.
      const previous = latest.get(record.cell_id);
      if (previous !== undefined) {
        executions.delete(previous);
      }
      latest.set(record.cell_id, record.id);
      const bound = new Map<Protocol.ItemId, Protocol.Variable>();
      for (const binding of bindings) {
        const id = `${record.id}:${binding.name}`;
        bound.set(id, {
          ...binding,
          id,
          execution_id: record.id,
          revision: { execution_id: record.id, update: 0 },
        });
      }
      if (bound.size) {
        variables.set(record.cell_id, bound);
      } else {
        variables.delete(record.cell_id);
      }
    }
    executions.set(record.id, {
      record,
      output: outputs.get(record.id) ?? null,
      outputVersion: 0,
      items: new Map(items.map((item) => [item.id, item])),
    });
  }
  const scratch = [...executions.values()].findLast(
    (execution) =>
      execution.record.cell_id === null && shown(execution) !== null,
  );
  return {
    variables,
    runs: new Map(),
    executions,
    latest,
    results: results(entries),
    scratch:
      scratch === undefined
        ? null
        : { record: scratch.record, output: scratch.output, outputVersion: 0 },
  };
}

function results(entries: ExecutionEntries): Results {
  const { records, outputs } = split(entries);
  const results = new Map<Protocol.CellId, Result | null>();
  for (const record of records) {
    if (record.cell_id !== null) {
      if (!results.has(record.cell_id)) {
        results.set(record.cell_id, null);
      }
      if (record.state.status === "completed") {
        results.set(record.cell_id, {
          record,
          output: outputs.get(record.id) ?? null,
          outputVersion: 0,
        });
      }
    }
  }
  return results;
}

export const MockExecutions = {
  T0,
  T1,
  execution,
  output,
  completed,

  /** A completed execution that took `elapsedMs`. */
  took(cellId: string, elapsedMs: number): Protocol.ExecutionOutput {
    return execution(cellId, {
      status: "completed",
      started_at: T0,
      completed_at: new Date(Date.parse(T0) + elapsedMs).toISOString(),
      outcome: SUCCEEDED,
      depends_on: {},
    });
  },

  /** A completed execution and the output it showed. */
  shown(
    cellId: string | null,
    display: Protocol.Media,
    fields: Partial<Omit<Protocol.ExecutionOutput, "id" | "state">> = {},
  ): readonly [Protocol.ExecutionOutput, Protocol.Output] {
    const execution = { ...completed(cellId), ...fields };
    return [execution, output(execution, display)];
  },

  /** A completed execution that ended in `error`, a ValueError by default. */
  failed(
    cellId: string,
    error: Partial<Protocol.ErrorOutput> = {},
  ): Protocol.ExecutionOutput {
    return completed(cellId, {
      kind: "failed",
      error: {
        kind: "exception",
        message: "boom",
        name: "ValueError",
        traceback: null,
        source: "marimo",
        severity: "error",
        range: null,
        related: [],
        ...error,
      },
    });
  },

  errored(cellId: string): Protocol.ExecutionOutput {
    return MockExecutions.failed(cellId);
  },

  interrupted(cellId: string | null): Protocol.ExecutionOutput {
    return completed(cellId, { kind: "cancelled" });
  },

  skipped(cellId: string): Protocol.ExecutionOutput {
    return completed(cellId, {
      kind: "skipped",
      reason: "ancestor-stopped",
      message: "",
      related: [],
    });
  },

  running(cellId: string | null): Protocol.ExecutionOutput {
    return execution(cellId, { status: "running", started_at: T0 });
  },

  queued(cellId: string | null): Protocol.ExecutionOutput {
    return execution(cellId, { status: "queued" });
  },

  notebook(id: Protocol.NotebookId = "n1"): Protocol.Notebook {
    return {
      id,
      project_id: "p1",
      path: null,
      name: "Notebook",
      operations: [],
      modified_at: null,
    };
  },

  runtime(state: Protocol.RuntimeState = READY): Protocol.Runtime {
    return {
      id: "r1",
      notebook_id: "n1",
      marimo_version: null,
      created_at: T0,
      state,
    };
  },

  /**
   * What the selectors read. `latest` and the results are derived from
   * `entries`, and the document is taken to have every cell they name,
   * with nothing keeping it from running.
   */
  inputs(
    entries: ExecutionEntries,
    extra: Partial<Pick<CellExecutionInputs, "requested" | "blocked">> = {},
  ): CellExecutionInputs {
    return {
      executions: mirror(entries),
      results: results(entries),
      cells: new Map(
        split(entries).records.flatMap((record) =>
          record.cell_id === null ? [] : [[record.cell_id, { config: CONFIG }]],
        ),
      ),
      requested: new Set(),
      blocked: new Set(),
      shownBlocked: new Set(),
      runtimeId: null,
      ...extra,
    };
  },

  /** Make the store's active replica report `entries`, `runtime`, and `document`. */
  seed(
    store: Store,
    entries: ExecutionEntries,
    runtime: Protocol.Runtime | null = null,
    document: Document | null = null,
  ) {
    const current = store.get(activeNotebookReplicaAtom);
    const documentAtom = atom<Document | null>(document);
    const replica = {
      attachmentsAtom: atom([]),
      connect: () => () => undefined,
      reconnect: () => Promise.resolve(),
      ...current,
      // Settable, so a test can close the connection or give the replica a
      // backend to command.
      connectionAtom: atom<ConnectionStatus>({ state: ConnectionState.OPEN }),
      generationAtom: atom(1),
      backendAtom: atom<NotebookBackend | null>(null),
      notebookAtom: atom<Protocol.Notebook | null>(MockExecutions.notebook()),
      analysisAtom: atom(null),
      documentAtom,
      shownDocumentAtom: documentAtom,
      runtimeAtom: atom(runtime),
      executionsAtom: atom(mirror(entries)),
      resultsAtom: atom(results(entries)),
    } satisfies NotebookReplica;
    store.set(activeNotebookReplicaAtom, replica);
    return replica;
  },
};
