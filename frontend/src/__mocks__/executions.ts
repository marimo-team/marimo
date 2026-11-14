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
  type Executions,
  type NotebookBackend,
  type NotebookReplica,
  type Results,
} from "@/core/notebook/replica";
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

function completed(
  cellId: string,
  overrides: Partial<Protocol.Execution> = {},
): Protocol.Execution {
  sequence += 1;
  return {
    id: `e${sequence}`,
    run_id: "run-1",
    runtime_id: "r1",
    caused_by: null,
    cell_id: cellId,
    code: null,
    code_fingerprint: "0f71456db2ea83f4",
    depends_on: {},
    status: "completed",
    outcome: { kind: "value", display: null },
    started_at: T0,
    completed_at: T1,
    ...overrides,
  };
}

function mirror(records: readonly Protocol.Execution[]): Executions {
  const executions = new Map<Protocol.ExecutionId, Execution>();
  const latest = new Map<Protocol.CellId, Protocol.ExecutionId>();
  for (const record of records) {
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
      items: new Map(),
      variables: new Map(),
    });
  }
  return { runs: new Map(), executions, latest };
}

function results(records: readonly Protocol.Execution[]): Results {
  const results = new Map<Protocol.CellId, Protocol.Execution>();
  for (const record of records) {
    if (record.cell_id !== null && record.status === "completed") {
      results.set(record.cell_id, record);
    }
  }
  return results;
}

export const MockExecutions = {
  T0,
  T1,
  completed,

  /** A completed execution that took `elapsedMs`. */
  took(cellId: string, elapsedMs: number): Protocol.Execution {
    return completed(cellId, {
      completed_at: new Date(Date.parse(T0) + elapsedMs).toISOString(),
    });
  },

  /** A completed execution that showed `display`. */
  shown(
    cellId: string,
    display: Protocol.DisplayData,
    overrides: Partial<Protocol.Execution> = {},
  ): Protocol.Execution {
    return completed(cellId, {
      outcome: { kind: "value", display },
      ...overrides,
    });
  },

  /** A completed execution that ended in `error`, a ValueError by default. */
  failed(
    cellId: string,
    error: Partial<Protocol.Error> = {},
    overrides: Partial<Protocol.Execution> = {},
  ): Protocol.Execution {
    return completed(cellId, {
      outcome: {
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
      },
      ...overrides,
    });
  },

  errored(cellId: string): Protocol.Execution {
    return MockExecutions.failed(cellId);
  },

  interrupted(cellId: string): Protocol.Execution {
    return completed(cellId, { outcome: { kind: "interrupted" } });
  },

  skipped(cellId: string): Protocol.Execution {
    return completed(cellId, {
      outcome: {
        kind: "skipped",
        reason: "ancestor-stopped",
        message: "",
        related: [],
      },
    });
  },

  running(cellId: string): Protocol.Execution {
    return completed(cellId, {
      status: "running",
      outcome: null,
      completed_at: null,
    });
  },

  queued(cellId: string): Protocol.Execution {
    return completed(cellId, {
      status: "queued",
      outcome: null,
      started_at: null,
      completed_at: null,
    });
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
      ...extra,
    };
  },

  /** Make the store's active replica report `records`, `runtime`, and `document`. */
  seed(
    store: Store,
    records: Protocol.Execution[],
    runtime: Protocol.Runtime | null = null,
    document: Document | null = null,
  ) {
    const current = store.get(activeNotebookReplicaAtom);
    const replica = {
      attachmentsAtom: atom([]),
      connect: () => () => undefined,
      reconnect: () => Promise.resolve(),
      ...current,
      // Settable, so a test can close the connection or give the replica a
      // backend to command.
      connectionAtom: atom<ConnectionStatus>({ state: ConnectionState.OPEN }),
      backendAtom: atom<NotebookBackend | null>(null),
      notebookAtom: atom<Protocol.Notebook | null>(MockExecutions.notebook()),
      documentAtom: atom<Document | null>(document),
      runtimeAtom: atom(runtime),
      executionsAtom: atom(mirror(records)),
      resultsAtom: atom(results(records)),
    } satisfies NotebookReplica;
    store.set(activeNotebookReplicaAtom, replica);
    return replica;
  },
};
