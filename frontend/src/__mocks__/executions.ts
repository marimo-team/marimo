/* Copyright 2026 Marimo. All rights reserved. */

/** Executions as the host would report them, for tests that read cell status. */

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
import { shownOutcome } from "@/core/notebook/replica";
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

const NO_VALUE: Protocol.ValueOutcome = { kind: "value", display: null };

function execution(
  cellId: string | null,
  state: Protocol.ExecutionState,
): Protocol.Execution {
  sequence += 1;
  return {
    id: `e${sequence}`,
    run_id: "run-1",
    runtime_id: "r1",
    caused_by: null,
    cell_id: cellId,
    code_fingerprint: "0f71456db2ea83f4",
    state,
  };
}

function completed(
  cellId: string | null,
  outcome: Protocol.Outcome = NO_VALUE,
): Protocol.Execution {
  return execution(cellId, {
    status: "completed",
    started_at: T0,
    completed_at: T1,
    outcome,
    depends_on: {},
  });
}

type ExecutionFixture = Protocol.Execution & { items?: readonly Item[] };

function mirror(records: readonly ExecutionFixture[]): Executions {
  const executions = new Map<Protocol.ExecutionId, Execution>();
  const latest = new Map<Protocol.CellId, Protocol.ExecutionId>();
  for (const { items = [], ...record } of records) {
    if (record.cell_id !== null) {
      // The host retains one execution per cell on the stream.
      const previous = latest.get(record.cell_id);
      if (previous !== undefined) {
        executions.delete(previous);
      }
      latest.set(record.cell_id, record.id);
    }
    executions.set(record.id, {
      record,
      outputVersion: 0,
      items: new Map(items.map((item) => [item.id, item])),
      variables: new Map(),
    });
  }
  const scratch = records.findLast(
    (record) => record.cell_id === null && shownOutcome(record) !== null,
  );
  return {
    runs: new Map(),
    executions,
    latest,
    results: results(records),
    scratch:
      scratch === undefined ? null : { record: scratch, outputVersion: 0 },
  };
}

function results(records: readonly Protocol.Execution[]): Results {
  const results = new Map<Protocol.CellId, Result | null>();
  for (const record of records) {
    if (record.cell_id !== null) {
      if (!results.has(record.cell_id)) {
        results.set(record.cell_id, null);
      }
      if (record.state.status === "completed") {
        results.set(record.cell_id, { record, outputVersion: 0 });
      }
    }
  }
  return results;
}

export const MockExecutions = {
  T0,
  T1,
  execution,
  completed,

  /** A completed execution that took `elapsedMs`. */
  took(cellId: string, elapsedMs: number): Protocol.Execution {
    return execution(cellId, {
      status: "completed",
      started_at: T0,
      completed_at: new Date(Date.parse(T0) + elapsedMs).toISOString(),
      outcome: NO_VALUE,
      depends_on: {},
    });
  },

  /** A completed execution that showed `display`. */
  shown(
    cellId: string | null,
    display: Protocol.DisplayData,
    fields: Partial<Omit<Protocol.Execution, "id" | "state">> = {},
  ): Protocol.Execution {
    return { ...completed(cellId, { kind: "value", display }), ...fields };
  },

  /** A completed execution that ended in `error`, a ValueError by default. */
  failed(
    cellId: string,
    error: Partial<Protocol.Error> = {},
  ): Protocol.Execution {
    return completed(cellId, {
      kind: "error",
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

  errored(cellId: string): Protocol.Execution {
    return MockExecutions.failed(cellId);
  },

  interrupted(cellId: string | null): Protocol.Execution {
    return completed(cellId, { kind: "interrupted" });
  },

  skipped(cellId: string): Protocol.Execution {
    return completed(cellId, {
      kind: "skipped",
      reason: "ancestor-stopped",
      message: "",
      related: [],
    });
  },

  /** A running execution that has shown `value` so far. */
  running(
    cellId: string | null,
    value: Protocol.ValueOutcome | null = null,
  ): Protocol.Execution {
    return execution(cellId, { status: "running", started_at: T0, value });
  },

  queued(cellId: string | null): Protocol.Execution {
    return execution(cellId, { status: "queued" });
  },

  notebook(id: Protocol.NotebookId = "n1"): Protocol.Notebook {
    return {
      id,
      project_id: "p1",
      path: null,
      name: "Notebook",
      operations: [],
      updated_at: null,
    };
  },

  runtime(status: Protocol.RuntimeStatus): Protocol.Runtime {
    return {
      id: "r1",
      notebook_id: "n1",
      status,
      message: null,
      marimo_version: null,
      started_at: T0,
    };
  },

  /**
   * What the selectors read. `latest` and the results are derived from
   * `records`, and the document is taken to have every cell they name,
   * with nothing keeping it from running.
   */
  inputs(
    records: readonly Protocol.Execution[],
    extra: Partial<Pick<CellExecutionInputs, "requested" | "blocked">> = {},
  ): CellExecutionInputs {
    return {
      executions: mirror(records),
      results: results(records),
      cells: new Map(
        records.flatMap((record) =>
          record.cell_id === null ? [] : [[record.cell_id, { config: CONFIG }]],
        ),
      ),
      requested: new Set(),
      blocked: new Set(),
      runtimeId: null,
      ...extra,
    };
  },

  /** Make the store's active replica report `records`, `runtime`, and `document`. */
  seed(
    store: Store,
    records: ExecutionFixture[],
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
      documentAtom,
      shownDocumentAtom: documentAtom,
      runtimeAtom: atom(runtime),
      executionsAtom: atom(mirror(records)),
      resultsAtom: atom(results(records)),
    } satisfies NotebookReplica;
    store.set(activeNotebookReplicaAtom, replica);
    return replica;
  },
};
