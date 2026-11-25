/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { NotebookResource } from "@marimo-team/client";
import {
  type Result,
  type Results,
  retainResult,
  retainScratchResult,
} from "./results";
import { shown, startedAt } from "../execution-state";

/** A console entry or input an execution produced, tagged by kind. */
type ProducedItem =
  | (Protocol.Console & { readonly kind: "console" })
  | (Protocol.Input & { readonly kind: "input" });

/** Time the host published the item, when included in a live event. */
export type Item = ProducedItem & { readonly time?: string };

/** An execution on the stream, with the items it has produced. */
export interface Execution extends Result {
  /** Items by id. `itemsInOrder` sorts them by `seq`. */
  readonly lastSeq?: number;
  /** Fast path for a reader displaying exactly the version before an append. */
  readonly append?: { before: WeakRef<Execution["items"]>; item: Item };
  readonly items: ReadonlyMap<Protocol.ItemId, Item>;
}

/**
 * Runs and executions as the stream reports them.
 *
 * Items and variables leave with their execution. Each cell's last result
 * stays for display while a new execution runs.
 */
export interface Executions {
  readonly runs: ReadonlyMap<Protocol.RunId, Protocol.RunOutput>;
  /** Every execution on the stream, scratch included. */
  readonly executions: ReadonlyMap<Protocol.ExecutionId, Execution>;
  /** The execution on the stream for each cell that has one. */
  readonly latest: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId>;
  /** Bindings by defining cell and item id, shared across unrelated stream updates. */
  readonly variables: ReadonlyMap<
    Protocol.CellId,
    ReadonlyMap<Protocol.ItemId, Protocol.Variable>
  >;
  readonly results: Results;
  readonly scratch: Result | null;
  /** The latest scratch execution to start, including one that printed nothing. */
  readonly scratchConsole?: Execution;
  /** The latest scratch run, if the host could not finish it and says why. */
  readonly scratchFailure?: RunFailure;
}

/** A run the host could not finish, with its reason. */
export interface RunFailure {
  readonly runId: Protocol.RunId;
  readonly message: string;
  readonly completedAt: string;
}

function hostFailure(run: Protocol.RunOutput): RunFailure | undefined {
  const { state } = run;
  return state.status === "completed" &&
    state.outcome.kind === "failed" &&
    state.outcome.message !== null
    ? {
        runId: run.id,
        message: state.outcome.message,
        completedAt: state.completed_at,
      }
    : undefined;
}

type Kind =
  | "cell"
  | "run"
  | "execution"
  | "output"
  | "console"
  | "input"
  | "variable";

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

function retainScratchConsole(
  state: Executions,
  execution: Execution,
): Execution | undefined {
  const current = state.scratchConsole;
  const { id, cell_id } = execution.record;
  const started_at = startedAt(execution.record);
  if (cell_id !== null || started_at === null) {
    return current;
  }
  if (!current || current.record.id === id) {
    return execution;
  }
  // A late write from an older execution cannot select its console again.
  const previous = state.executions.get(id);
  if (previous && startedAt(previous.record) !== null) {
    return current;
  }
  return Date.parse(started_at) >= Date.parse(startedAt(current.record) ?? "")
    ? execution
    : current;
}

/** Replace an execution on the stream, indexed under its cell. */
function set(state: Executions, execution: Execution): Executions {
  const { id, cell_id: cellId } = execution.record;
  return {
    ...state,
    executions: new Map(state.executions).set(id, execution),
    scratchConsole: retainScratchConsole(state, execution),
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
  const isLatest = cellId !== null && state.latest.get(cellId) === id;
  return {
    ...state,
    executions: without(state.executions, id),
    variables: isLatest ? without(state.variables, cellId) : state.variables,
    scratchConsole:
      state.scratchConsole?.record.id === id ? undefined : state.scratchConsole,
    latest: isLatest ? without(state.latest, cellId) : state.latest,
  };
}

function attach(state: Executions, item: Item): Executions {
  const execution = state.executions.get(item.execution_id);
  if (execution === undefined) {
    return state;
  }
  // Updating an input's status keeps the prompt at its original position.
  const original = execution.items.get(item.id);
  if (original) {
    item = { ...item, time: original.time };
  }
  return set(state, {
    ...execution,
    append:
      !original && item.seq > (execution.lastSeq ?? -1)
        ? { before: new WeakRef(execution.items), item }
        : undefined,
    lastSeq: Math.max(execution.lastSeq ?? -1, item.seq),
    items: new Map(execution.items).set(item.id, item),
  });
}

function detach(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const execution of state.executions.values()) {
    if (execution.items.has(itemId)) {
      return set(state, {
        ...execution,
        append: undefined,
        items: without(execution.items, itemId),
      });
    }
  }
  return state;
}

function bind(state: Executions, variable: Protocol.Variable): Executions {
  const cellId = state.executions.get(variable.execution_id)?.record.cell_id;
  if (cellId == null) {
    return state;
  }
  const bindings = new Map(state.variables.get(cellId)).set(
    variable.id,
    variable,
  );
  return {
    ...state,
    variables: new Map(state.variables).set(cellId, bindings),
  };
}

function unbind(state: Executions, itemId: Protocol.ItemId): Executions {
  for (const [cellId, bindings] of state.variables) {
    if (bindings.has(itemId)) {
      const variables = new Map(state.variables);
      if (bindings.size === 1) {
        variables.delete(cellId);
      } else {
        variables.set(cellId, without(bindings, itemId));
      }
      return { ...state, variables };
    }
  }
  return state;
}

function sameShown(
  a: Pick<Result, "record" | "output">,
  b: Pick<Result, "record" | "output">,
): boolean {
  return JSON.stringify(shown(a)) === JSON.stringify(shown(b));
}

/** Replace an execution and keep its retained copies in step. */
function update(state: Executions, execution: Execution): Executions {
  return {
    ...set(state, execution),
    results: retainResult(state.results, execution),
    scratch: retainScratchResult(state.scratch, execution),
  };
}

/** Carry displayed results and their revisions through a replacement snapshot. */
export function resumeResults(
  next: Executions,
  previous: Executions,
  runtimeId: Protocol.RuntimeId | undefined,
): Executions {
  const resumed = new Map(next.executions);
  for (const [id, execution] of resumed) {
    const retained =
      execution.record.cell_id === null
        ? previous.scratch
        : previous.results.get(execution.record.cell_id);
    const before =
      previous.executions.get(id) ??
      (retained?.record.id === id ? retained : undefined);
    if (before !== undefined) {
      resumed.set(id, {
        ...execution,
        outputVersion:
          before.outputVersion + (sameShown(before, execution) ? 0 : 1),
      });
    }
  }
  const results = new Map(next.results);
  for (const [cellId, result] of results) {
    const execution =
      result === null ? undefined : resumed.get(result.record.id);
    results.set(
      cellId,
      execution === undefined
        ? (previous.results.get(cellId) ?? null)
        : {
            record: execution.record,
            output: execution.output,
            outputVersion: execution.outputVersion,
          },
    );
  }
  const scratch =
    next.scratch === null ? null : resumed.get(next.scratch.record.id);
  return {
    ...next,
    executions: resumed,
    results,
    scratchConsole:
      next.scratchConsole ??
      (previous.scratchConsole?.record.state.status === "completed" &&
      previous.scratchConsole.record.runtime_id === runtimeId
        ? previous.scratchConsole
        : undefined),
    scratch:
      scratch == null
        ? previous.scratch
        : retainScratchResult(previous.scratch, scratch),
  };
}

export const executions: NotebookResource<Executions, Kind> = {
  initial: {
    runs: new Map(),
    executions: new Map(),
    latest: new Map(),
    variables: new Map(),
    results: new Map(),
    scratch: null,
  },
  on: {
    cell: (state, { data }) =>
      state.results.has(data.cell.id)
        ? state
        : { ...state, results: new Map(state.results).set(data.cell.id, null) },
    "cell.removed": (state, { data }) => ({
      ...state,
      results: without(state.results, data.id),
    }),
    run: (state, { data }) => ({
      ...state,
      runs: new Map(state.runs).set(data.run.id, data.run),
      // A newer scratch run replaces what the last one reported.
      scratchFailure:
        data.run.origin.kind === "code"
          ? hostFailure(data.run)
          : state.scratchFailure,
    }),
    "run.removed": (state, { data }) =>
      state.runs.has(data.id)
        ? { ...state, runs: without(state.runs, data.id) }
        : state,
    execution: (state, { data: { execution: record } }) => {
      const previous = state.executions.get(record.id);
      const next = { record, output: previous?.output ?? null };
      return update(state, {
        ...next,
        outputVersion:
          previous === undefined
            ? 0
            : previous.outputVersion + (sameShown(previous, next) ? 0 : 1),
        append: previous?.append,
        lastSeq: previous?.lastSeq,
        items: previous?.items ?? new Map(),
      });
    },
    "execution.removed": (state, { data }) => remove(state, data.id),
    output: (state, { data: { output } }) => {
      const execution = state.executions.get(output.execution_id);
      if (execution === undefined) {
        return state;
      }
      const next = { ...execution, output };
      return update(state, {
        ...next,
        outputVersion:
          execution.outputVersion + (sameShown(execution, next) ? 0 : 1),
      });
    },
    // The output leaves with its execution, and a retained result keeps its copy.
    "output.removed": (state) => state,
    console: (state, { data }) =>
      attach(state, { ...data.console, kind: "console", time: data.time }),
    "console.removed": (state, { data }) => detach(state, data.id),
    input: (state, { data }) =>
      attach(state, { ...data.input, kind: "input", time: data.time }),
    variable: (state, { data }) => bind(state, data.variable),
    "variable.removed": (state, { data }) => unbind(state, data.id),
  },
};
