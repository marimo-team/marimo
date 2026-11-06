/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Whether each cell's result still reflects the document and the values
 * it read, by the host protocol's rules.
 *
 * A completed execution is current when its code fingerprint equals the
 * cell's, every variable it depends on still holds the recorded revision,
 * every name it depends on that was unbound is still unbound, and the
 * executions that bound those variables are current. See the freshness
 * section of `protocols/host/spec.md`.
 *
 * The protocol also ranks why a result is outdated. The editor asks two
 * questions of its own, so that is what this reports; the ranked reason
 * can come back with a reader. Two editor concerns are folded in: a name
 * bound only by an earlier runtime is unbound in this one, and a queued or
 * running execution for the cell's current source already covers it.
 */

import type * as Protocol from "@marimo-team/client/protocol";
import type { Executions, Results } from "@/core/notebook/replica";

export interface CellFreshness {
  /** This cell's source changed since its result. */
  readonly sourceChanged: boolean;
  /**
   * A value the result read changed since, by a rerun or an update, here
   * or upstream. An ancestor that was only edited does not count: its
   * values are still the ones this result read.
   */
  readonly inputsChanged: boolean;
}

/** Current, and also a cell with no completed execution to compare. */
const CURRENT: CellFreshness = { sourceChanged: false, inputsChanged: false };

/** What freshness is derived from. */
export interface CellFreshnessInputs {
  /** The document's cells, for the fingerprint of each cell's source. */
  readonly cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>;
  /** The stream's executions, for the variables currently bound. */
  readonly executions: Executions;
  /** Each cell's last completed record, the result being compared. */
  readonly results: Results;
}

/** Freshness by cell id, as `freshnessOf` builds it. */
export type CellFreshnessLookup = (id: Protocol.CellId) => CellFreshness;

/** The variables bound in the namespace right now, by name. */
function boundVariables(
  executions: Executions,
): ReadonlyMap<string, Protocol.Variable[]> {
  const byName = new Map<string, Protocol.Variable[]>();
  for (const execution of executions.executions.values()) {
    for (const variable of execution.variables.values()) {
      const bound = byName.get(variable.name);
      if (bound === undefined) {
        byName.set(variable.name, [variable]);
      } else {
        bound.push(variable);
      }
    }
  }
  return byName;
}

/**
 * Compares results against the document and the namespace.
 *
 * Build one per set of inputs and ask it about each cell, since the
 * bound variables are indexed once and a binding execution's freshness is
 * computed once however many results depend on it.
 */
export function freshnessOf(inputs: CellFreshnessInputs): CellFreshnessLookup {
  const bound = boundVariables(inputs.executions);
  const memo = new Map<Protocol.ExecutionId, CellFreshness>();
  const recordOf = (id: Protocol.ExecutionId) =>
    inputs.executions.executions.get(id)?.record;

  /** Whether a value the record read has changed, or one upstream has. */
  function inputsChanged(
    record: Protocol.Execution,
    visiting: ReadonlySet<Protocol.ExecutionId>,
  ): boolean {
    const path = new Set(visiting).add(record.id);
    for (const [name, revision] of Object.entries(record.depends_on)) {
      const variables = bound.get(name) ?? [];
      if (revision === null) {
        // A result retained from an earlier runtime binds nothing here.
        if (
          variables.some(
            (v) => recordOf(v.execution_id)?.runtime_id === record.runtime_id,
          )
        ) {
          return true;
        }
        continue;
      }
      const variable = variables.find(
        (candidate) => candidate.revision.execution === revision.execution,
      );
      if (
        variable === undefined ||
        variable.revision.update !== revision.update
      ) {
        return true;
      }
      const binder = recordOf(variable.execution_id);
      if (binder === undefined) {
        return true;
      }
      if (!path.has(binder.id) && ofRecord(binder, path).inputsChanged) {
        return true;
      }
    }
    return false;
  }

  /** Whether a newer execution of the cell already runs its current source. */
  function coveredByPending(
    cell: Protocol.Cell,
    record: Protocol.Execution,
  ): boolean {
    const latest = inputs.executions.latest.get(cell.id);
    if (latest === undefined || latest === record.id) {
      return false;
    }
    const pending = recordOf(latest);
    return (
      pending !== undefined &&
      pending.status !== "completed" &&
      pending.code_fingerprint === cell.code_fingerprint
    );
  }

  function ofRecord(
    record: Protocol.Execution,
    visiting: ReadonlySet<Protocol.ExecutionId>,
  ): CellFreshness {
    const known = memo.get(record.id);
    if (known !== undefined) {
      return known;
    }
    const cell =
      record.cell_id === null ? undefined : inputs.cells.get(record.cell_id);
    const freshness: CellFreshness = {
      sourceChanged:
        cell === undefined ||
        (cell.code_fingerprint !== record.code_fingerprint &&
          !coveredByPending(cell, record)),
      inputsChanged: inputsChanged(record, visiting),
    };
    memo.set(record.id, freshness);
    return freshness;
  }

  return (id) => {
    const result = inputs.results.get(id);
    return result === null || result === undefined
      ? CURRENT
      : ofRecord(result, new Set());
  };
}
