/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookResource } from "@marimo-team/client";

/** A console line, display, or input an execution produced, tagged by kind. */
export type Item =
  | (Protocol.Console & { readonly kind: "console" })
  | (Protocol.Display & { readonly kind: "display" })
  | (Protocol.Input & { readonly kind: "input" });

/** An execution on the stream, with the items and variables it has produced. */
export interface Execution {
  readonly record: Protocol.Execution;
  /** Items by id. `itemsInOrder` sorts them by `seq`. */
  readonly items: ReadonlyMap<Protocol.ItemId, Item>;
  /** The variables the execution bound, by item id. */
  readonly variables: ReadonlyMap<Protocol.ItemId, Protocol.Variable>;
}

/**
 * Runs and executions as the stream reports them.
 *
 * Nothing outlives its removal. The host removes a cell's previous
 * execution before it publishes the next one, so `results` keeps each
 * cell's last completed record for display.
 */
export interface Executions {
  readonly runs: ReadonlyMap<Protocol.RunId, Protocol.Run>;
  /** Every execution on the stream, scratch included. */
  readonly executions: ReadonlyMap<Protocol.ExecutionId, Execution>;
  /** The execution on the stream for each cell that has one. */
  readonly latest: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId>;
}

type Kind = "run" | "execution" | "console" | "display" | "input" | "variable";

/** An execution's items in the order they were produced. */
export function itemsInOrder(execution: Pick<Execution, "items">): Item[] {
  return [...execution.items.values()].toSorted((a, b) => a.seq - b.seq);
}

function without<K, V>(map: ReadonlyMap<K, V>, key: K): ReadonlyMap<K, V> {
  if (!map.has(key)) {
    return map;
  }
  const next = new Map(map);
  next.delete(key);
  return next;
}

/** Replace an execution on the stream, indexed under its cell. */
function set(state: Executions, execution: Execution): Executions {
  const { id, cell_id: cellId } = execution.record;
  return {
    ...state,
    executions: new Map(state.executions).set(id, execution),
    latest:
      cellId === null || state.latest.get(cellId) === id
        ? state.latest
        : new Map(state.latest).set(cellId, id),
  };
}

function remove(state: Executions, id: Protocol.ExecutionId): Executions {
  const execution = state.executions.get(id);
  if (execution === undefined) {
    return state;
  }
  const cellId = execution.record.cell_id;
  return {
    ...state,
    executions: without(state.executions, id),
    latest:
      cellId !== null && state.latest.get(cellId) === id
        ? without(state.latest, cellId)
        : state.latest,
  };
}

function attach(state: Executions, item: Item): Executions {
  const execution = state.executions.get(item.execution_id);
  if (execution === undefined) {
    return state;
  }
  return set(state, {
    ...execution,
    items: new Map(execution.items).set(item.id, item),
  });
}

function detach(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const execution of state.executions.values()) {
    if (execution.items.has(itemId)) {
      return set(state, {
        ...execution,
        items: without(execution.items, itemId),
      });
    }
  }
  return state;
}

function bind(state: Executions, variable: Protocol.Variable): Executions {
  const execution = state.executions.get(variable.execution_id);
  if (execution === undefined) {
    return state;
  }
  return set(state, {
    ...execution,
    variables: new Map(execution.variables).set(variable.id, variable),
  });
}

function unbind(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const execution of state.executions.values()) {
    if (execution.variables.has(itemId)) {
      return set(state, {
        ...execution,
        variables: without(execution.variables, itemId),
      });
    }
  }
  return state;
}

export const executions: NotebookResource<Executions, Kind> = {
  initial: { runs: new Map(), executions: new Map(), latest: new Map() },
  on: {
    run: (state, { data }) => ({
      ...state,
      runs: new Map(state.runs).set(data.run.id, data.run),
    }),
    "run.removed": (state, { data }) =>
      state.runs.has(data.id)
        ? { ...state, runs: without(state.runs, data.id) }
        : state,
    execution: (state, { data: { execution: record } }) => {
      const previous = state.executions.get(record.id);
      return set(state, {
        record,
        items: previous?.items ?? new Map(),
        variables: previous?.variables ?? new Map(),
      });
    },
    "execution.removed": (state, { data }) => remove(state, data.id),
    console: (state, { data }) =>
      attach(state, { ...data.console, kind: "console" }),
    "console.removed": (state, { data }) => detach(state, data.id),
    display: (state, { data }) =>
      attach(state, { ...data.display, kind: "display" }),
    "display.removed": (state, { data }) => detach(state, data.id),
    input: (state, { data }) => attach(state, { ...data.input, kind: "input" }),
    variable: (state, { data }) => bind(state, data.variable),
    "variable.removed": (state, { data }) => unbind(state, data.id),
  },
};
