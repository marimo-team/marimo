/* Copyright 2026 Marimo. All rights reserved. */

/**
 * What a cell shows in its output area, read from the host's executions.
 *
 * A completed result's outcome is the output. While the cell runs again,
 * the running execution's value so far takes its place, so appended
 * output appears as it arrives. The view keeps the message shape the
 * renderers take, so they need not know where it came from.
 */

import type * as Protocol from "@marimo-team/client/protocol";
import type { CellId } from "@/core/cells/ids";
import type { MarimoError, OutputMessage } from "@/core/kernel/messages";
import type { Executions, Result, Results } from "@/core/notebook/replica";
import { completedAt, shown, startedAt } from "@/core/notebook/replica";

/** A host error shown as its message and the cells involved. */
export interface HostDiagnostic {
  readonly type: "diagnostic";
  readonly kind: string;
  readonly msg: string;
  readonly related: readonly {
    readonly cell_id: CellId;
    readonly message: string;
  }[];
}

/** An error the output area renders: a kernel shape or a host diagnostic. */
export type CellError = MarimoError | HostDiagnostic;

/** An output message whose error data may carry host diagnostics. */
export type CellOutput = Omit<OutputMessage, "data"> & {
  readonly data: OutputMessage["data"] | readonly CellError[];
};

/** The execution and display revision hidden by this browser. */
export interface ClearedOutput {
  readonly execution: Protocol.ExecutionId;
  readonly version: number;
}

export interface CellOutputInputs {
  readonly executions: Executions;
  readonly results: Results;
  /** What each cell showed when this browser cleared it. */
  readonly cleared: ReadonlyMap<Protocol.CellId, ClearedOutput>;
  /** The confirmed document's cells, for the source an execution ran. */
  readonly cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>;
}

const NO_CELLS: ReadonlyMap<Protocol.CellId, Protocol.Cell> = new Map();

const ERROR_MIMETYPE = "application/vnd.marimo+error";

function related(
  cells: readonly Protocol.RelatedOutput[],
): HostDiagnostic["related"] {
  return cells.map(({ cell_id, message }) => ({
    cell_id: cell_id,
    message,
  }));
}

function seconds(iso: string | null): number {
  return iso === null ? 0 : Date.parse(iso) / 1000;
}

function endedAt(record: Protocol.ExecutionOutput): number {
  return seconds(completedAt(record) ?? startedAt(record));
}

function valueOutput(
  record: Protocol.ExecutionOutput,
  value: Protocol.Media,
): CellOutput {
  return {
    channel: "output",
    mimetype: value.mimetype as OutputMessage["mimetype"],
    data: value.data,
    timestamp: endedAt(record),
  };
}

function errorOutput(
  record: Protocol.ExecutionOutput,
  data: CellError[],
): CellOutput {
  return {
    channel: "marimo-error",
    mimetype: ERROR_MIMETYPE,
    data,
    timestamp: endedAt(record),
  };
}

/** The cell an exception was blamed on, which is the one cell the host relates to it. */
function raisingCell(error: Protocol.ErrorOutput): CellId | null {
  return error.related.at(0)?.cell_id ?? null;
}

/**
 * A host error in the shape the output area renders.
 *
 * Exceptions, syntax errors, and internal errors keep the kernel's shapes,
 * which the renderer treats with their own affordances. Every other kind
 * is a diagnostic.
 */
export function cellError(error: Protocol.ErrorOutput): CellError {
  switch (error.kind) {
    case "exception":
      return {
        type: "exception",
        exception_type: error.name ?? "Exception",
        msg: error.message,
        raising_cell: raisingCell(error),
        traceback: error.traceback?.data ?? null,
      };
    case "invalid-syntax":
      return {
        type: "syntax",
        msg: error.message,
        lineno: error.range === null ? null : error.range.start.line + 1,
      };
    case "internal":
      return { type: "unknown", msg: error.message, error_type: error.name };
    default:
      return {
        type: "diagnostic",
        kind: error.kind,
        msg: error.message,
        related: related(error.related),
      };
  }
}

/** The notice a skipped cell shows in place of a value. */
function skippedOutput(
  record: Protocol.ExecutionOutput,
  outcome: Protocol.ExecutionSkippedOutcomeOutput,
): CellOutput {
  const cause = outcome.related[0];
  if (cause !== undefined && outcome.reason === "upstream-stopped") {
    return errorOutput(record, [
      {
        type: "ancestor-stopped",
        msg: outcome.message,
        raising_cell: cause.cell_id,
      },
    ]);
  }
  if (cause !== undefined && outcome.reason === "upstream-failed") {
    const blamed = outcome.related
      .slice(1)
      .find((cell) => cell.cell_id !== record.cell_id);
    return errorOutput(record, [
      {
        type: "ancestor-prevented",
        msg: outcome.message,
        raising_cell: cause.cell_id,
        blamed_cell: blamed === undefined ? null : blamed.cell_id,
      },
    ]);
  }
  return errorOutput(record, [
    {
      type: "diagnostic",
      kind: outcome.reason,
      msg: outcome.message,
      related: related(outcome.related),
    },
  ]);
}

/**
 * The source an execution ran, while the confirmed cell still has it.
 *
 * Fingerprints are opaque, so the editor cannot take one of its draft. The
 * confirmed cell's fingerprint names the source the host holds, which is
 * the execution's own until an edit is confirmed.
 */
export function executionSource(
  record: Protocol.ExecutionOutput,
  cells: ReadonlyMap<Protocol.CellId, Protocol.Cell> = NO_CELLS,
): string | undefined {
  const cell = record.cell_id === null ? undefined : cells.get(record.cell_id);
  return cell !== undefined &&
    cell.code !== null &&
    cell.code_fingerprint === record.code_fingerprint
    ? cell.code
    : undefined;
}

/**
 * What a result shows, or null for an empty output, with the source it ran
 * when `cells` still holds it.
 */
export function resultOutput(
  result: Result,
  cells: ReadonlyMap<Protocol.CellId, Protocol.Cell> = NO_CELLS,
): CellOutput | null {
  const output = resultDisplay(result);
  const code = executionSource(result.record, cells);
  return output === null || code === undefined ? output : { ...output, code };
}

function resultDisplay(result: Result): CellOutput | null {
  const { record } = result;
  const showing = shown(result);
  if (showing === null) {
    return null;
  }
  switch (showing.kind) {
    case "output":
      return showing.media === null ? null : valueOutput(record, showing.media);
    case "failed":
      return errorOutput(record, [cellError(showing.error)]);
    case "cancelled":
      return errorOutput(record, [{ type: "interruption" }]);
    case "skipped":
      return skippedOutput(record, showing);
  }
}

/**
 * The execution whose outcome a cell shows: its running one once that has
 * shown something, else its result.
 *
 * A running execution has no output until it sets one, so the result stays
 * up until then. Once it has, an empty output means the cell cleared it,
 * and nothing shows. A result that says the
 * cell did not run comes down as soon as it does run.
 */
export function shownExecution(
  inputs: Pick<CellOutputInputs, "executions" | "results">,
  id: Protocol.CellId,
): Result | null {
  const latestId = inputs.executions.latest.get(id);
  const latest =
    latestId === undefined
      ? undefined
      : inputs.executions.executions.get(latestId);
  if (
    latest !== undefined &&
    shown(latest) !== null &&
    latest.record.state.status !== "completed"
  ) {
    return latest;
  }
  const result = inputs.results.get(id) ?? null;
  if (
    latest?.record.state.status === "running" &&
    result !== null &&
    shown(result)?.kind === "skipped"
  ) {
    return null;
  }
  return result;
}

/**
 * Whether `record` still shows what was cleared.
 *
 * A running execution that shows something new after the clear comes back,
 * and so does a newer execution.
 */
function stillCleared(
  cleared: ClearedOutput | undefined,
  shown: Result,
): boolean {
  return (
    cleared?.execution === shown.record.id &&
    cleared.version === shown.outputVersion
  );
}

/** What a cell shows, unless this browser cleared it. */
export function cellOutputView(
  inputs: CellOutputInputs,
  id: Protocol.CellId,
): CellOutput | null {
  const showing = shownExecution(inputs, id);
  if (showing === null || stillCleared(inputs.cleared.get(id), showing)) {
    return null;
  }
  return resultOutput(showing, inputs.cells);
}

/**
 * What each cell with a result or a running execution shows, by cell id.
 *
 * Cells showing nothing are left out, so a reader can tell "no output"
 * from "has a cell" without the document.
 */
export function cellOutputsView(
  inputs: CellOutputInputs,
): ReadonlyMap<CellId, CellOutput> {
  const outputs = new Map<CellId, CellOutput>();
  const cellIds = new Set([
    ...inputs.results.keys(),
    ...inputs.executions.latest.keys(),
  ]);
  for (const cellId of cellIds) {
    const output = cellOutputView(inputs, cellId);
    if (output !== null) {
      outputs.set(cellId, output);
    }
  }
  return outputs;
}

/**
 * The latest scratch display, retained until a newer execution shows one.
 */
export function scratchOutputView(executions: Executions): CellOutput | null {
  const failure = executions.scratchFailure;
  // A run that failed before the kernel saw its code has no execution to
  // show, so its own reason stands in for the result.
  if (
    failure !== undefined &&
    executions.scratch?.record.run_id !== failure.runId
  ) {
    return {
      channel: "marimo-error",
      mimetype: ERROR_MIMETYPE,
      data: [{ type: "unknown", msg: failure.message, error_type: null }],
      timestamp: seconds(failure.completedAt),
    };
  }
  return executions.scratch === null ? null : resultOutput(executions.scratch);
}
