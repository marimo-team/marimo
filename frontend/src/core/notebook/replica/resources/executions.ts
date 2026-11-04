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
 * A cell execution as it last completed, kept after the host removes it.
 *
 * The host removes a cell's previous execution, items first, before it
 * publishes the next one. A result ignores removals, so retiring cannot
 * strip it, and takes items the execution adds or replaces afterwards.
 * Its inputs are answered or cancelled, since the host cancels pending
 * ones before completion. Variables stay with the stream's copy, as
 * freshness compares what the host holds now.
 */
export interface Result {
  readonly record: Protocol.Execution;
  readonly items: ReadonlyMap<Protocol.ItemId, Item>;
}

/** A document cell's execution on the stream and its last completed result. */
export interface CellResult {
  /** The cell's execution on the stream, in any status. */
  readonly latest: Execution | null;
  /** The last execution that completed, until the cell leaves the document. */
  readonly completed: Result | null;
}

/** Runs and executions on the stream, and each document cell's result. */
export interface Executions {
  readonly runs: ReadonlyMap<Protocol.RunId, Protocol.Run>;
  /** Every execution on the stream, scratch included. */
  readonly executions: ReadonlyMap<Protocol.ExecutionId, Execution>;
  /** One entry per cell, from its `cell` event until its removal. */
  readonly cells: ReadonlyMap<Protocol.CellId, CellResult>;
}

type Kind =
  | "cell"
  | "run"
  | "execution"
  | "console"
  | "display"
  | "input"
  | "variable";

/** An execution's items in the order they were produced. */
export function itemsInOrder(execution: Pick<Execution, "items">): Item[] {
  return [...execution.items.values()].toSorted((a, b) => a.seq - b.seq);
}

const NO_RESULT: CellResult = { latest: null, completed: null };

function without<K, V>(map: ReadonlyMap<K, V>, key: K): ReadonlyMap<K, V> {
  if (!map.has(key)) {
    return map;
  }
  const next = new Map(map);
  next.delete(key);
  return next;
}

/** The cell's entry after `execution` changed on the stream. */
function view(
  entry: CellResult,
  execution: Execution,
  adopt: boolean,
): CellResult {
  const { id, status } = execution.record;
  if (!adopt && entry.latest?.record.id !== id) {
    return entry;
  }
  return {
    latest: execution,
    completed:
      status === "completed"
        ? { record: execution.record, items: execution.items }
        : entry.completed,
  };
}

/** Put `execution` on the stream. `adopt` makes it its cell's latest. */
function publish(
  state: Executions,
  execution: Execution,
  adopt: boolean,
): Executions {
  const { id, cell_id: cellId } = execution.record;
  const executions = new Map(state.executions).set(id, execution);
  const entry = cellId === null ? undefined : state.cells.get(cellId);
  if (cellId === null || entry === undefined) {
    return { ...state, executions };
  }
  const next = view(entry, execution, adopt);
  return next === entry
    ? { ...state, executions }
    : { ...state, executions, cells: new Map(state.cells).set(cellId, next) };
}

/** Take an item removal on the stream's copy. A result keeps what it had. */
function strip(
  state: Executions,
  execution: Execution,
  next: Execution,
): Executions {
  const { id, cell_id: cellId } = execution.record;
  const executions = new Map(state.executions).set(id, next);
  const entry = cellId === null ? undefined : state.cells.get(cellId);
  if (
    cellId === null ||
    entry === undefined ||
    entry.latest?.record.id !== id
  ) {
    return { ...state, executions };
  }
  return {
    ...state,
    executions,
    cells: new Map(state.cells).set(cellId, { ...entry, latest: next }),
  };
}

function attach(state: Executions, item: Item): Executions {
  const execution = state.executions.get(item.execution_id);
  if (execution === undefined) {
    return state;
  }
  return publish(
    state,
    { ...execution, items: new Map(execution.items).set(item.id, item) },
    false,
  );
}

function detach(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const execution of state.executions.values()) {
    if (execution.items.has(itemId)) {
      return strip(state, execution, {
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
  return publish(
    state,
    {
      ...execution,
      variables: new Map(execution.variables).set(variable.id, variable),
    },
    false,
  );
}

function unbind(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const execution of state.executions.values()) {
    if (execution.variables.has(itemId)) {
      return strip(state, execution, {
        ...execution,
        variables: without(execution.variables, itemId),
      });
    }
  }
  return state;
}

/** Take an execution off the stream. Its cell keeps its last result. */
function remove(state: Executions, id: Protocol.ExecutionId): Executions {
  const execution = state.executions.get(id);
  if (execution === undefined) {
    return state;
  }
  const executions = without(state.executions, id);
  const cellId = execution.record.cell_id;
  const entry = cellId === null ? undefined : state.cells.get(cellId);
  if (
    cellId === null ||
    entry === undefined ||
    entry.latest?.record.id !== id
  ) {
    return { ...state, executions };
  }
  return {
    ...state,
    executions,
    cells: new Map(state.cells).set(cellId, { ...entry, latest: null }),
  };
}

/** Describe a cell from the execution the stream already holds for it, if any. */
function describe(state: Executions, cellId: Protocol.CellId): CellResult {
  for (const execution of state.executions.values()) {
    if (execution.record.cell_id === cellId) {
      return view(NO_RESULT, execution, true);
    }
  }
  return NO_RESULT;
}

export const executions: NotebookResource<Executions, Kind> = {
  initial: { runs: new Map(), executions: new Map(), cells: new Map() },
  on: {
    cell: (state, { data }) =>
      state.cells.has(data.cell.id)
        ? state
        : {
            ...state,
            cells: new Map(state.cells).set(
              data.cell.id,
              describe(state, data.cell.id),
            ),
          },
    "cell.removed": (state, { data }) =>
      state.cells.has(data.id)
        ? { ...state, cells: without(state.cells, data.id) }
        : state,
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
      return publish(
        state,
        {
          record,
          items: previous?.items ?? new Map(),
          variables: previous?.variables ?? new Map(),
        },
        true,
      );
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
