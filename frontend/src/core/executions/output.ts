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
import type { Executions, Results } from "@/core/notebook/replica";

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

/** What every cell's output derives from. */
export interface CellOutputInputs {
  readonly executions: Executions;
  readonly results: Results;
  /** Results this browser cleared, by execution id, until a newer one lands. */
  readonly cleared: ReadonlyMap<Protocol.CellId, Protocol.ExecutionId>;
  /** The confirmed document's cells, for the source an execution ran. */
  readonly cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>;
}

const NO_CELLS: ReadonlyMap<Protocol.CellId, Protocol.Cell> = new Map();

const ERROR_MIMETYPE = "application/vnd.marimo+error";

/** The protocol's ids are plain strings; the editor brands them. */
function brand(id: Protocol.CellId): CellId {
  return id as CellId;
}

function related(
  cells: readonly Protocol.Related[],
): HostDiagnostic["related"] {
  return cells.map(({ cell_id, message }) => ({
    cell_id: brand(cell_id),
    message,
  }));
}

function seconds(iso: string | null): number {
  return iso === null ? 0 : Date.parse(iso) / 1000;
}

function endedAt(record: Protocol.Execution): number {
  return seconds(record.completed_at ?? record.started_at);
}

function valueOutput(
  record: Protocol.Execution,
  value: Protocol.DisplayData,
): CellOutput {
  return {
    channel: "output",
    mimetype: value.mimetype as OutputMessage["mimetype"],
    data: value.data,
    timestamp: endedAt(record),
  };
}

function errorOutput(
  record: Protocol.Execution,
  data: CellError[],
): CellOutput {
  return {
    channel: "marimo-error",
    mimetype: ERROR_MIMETYPE,
    data,
    timestamp: endedAt(record),
  };
}

/** The cell an exception was blamed on, when the host names one. */
function raisingCell(error: Protocol.Error): CellId | null {
  const raised = error.related.find((cell) => cell.message === "raised");
  return raised === undefined ? null : brand(raised.cell_id);
}

/**
 * A host error in the shape the output area renders.
 *
 * Exceptions, syntax errors, and internal errors keep the kernel's shapes,
 * which the renderer treats with their own affordances. Every other kind
 * is a diagnostic.
 */
export function cellError(error: Protocol.Error): CellError {
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
    case "interrupted":
      return { type: "interruption" };
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
  record: Protocol.Execution,
  outcome: Protocol.SkippedOutcome,
): CellOutput {
  const cause = outcome.related[0];
  if (cause !== undefined && outcome.reason === "upstream-stopped") {
    return errorOutput(record, [
      {
        type: "ancestor-stopped",
        msg: outcome.message,
        raising_cell: brand(cause.cell_id),
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
        raising_cell: brand(cause.cell_id),
        blamed_cell: blamed === undefined ? null : brand(blamed.cell_id),
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
function sourceOf(
  record: Protocol.Execution,
  cells: ReadonlyMap<Protocol.CellId, Protocol.Cell>,
): string | undefined {
  const cell = record.cell_id === null ? undefined : cells.get(record.cell_id);
  return cell !== undefined &&
    cell.code !== null &&
    cell.code_fingerprint === record.code_fingerprint
    ? cell.code
    : undefined;
}

/**
 * What an execution's outcome shows, or null for an empty value, with the
 * source it ran when `cells` still holds it.
 */
export function outcomeOutput(
  record: Protocol.Execution,
  cells: ReadonlyMap<Protocol.CellId, Protocol.Cell> = NO_CELLS,
): CellOutput | null {
  const output = outcomeDisplay(record);
  const code = sourceOf(record, cells);
  return output === null || code === undefined ? output : { ...output, code };
}

function outcomeDisplay(record: Protocol.Execution): CellOutput | null {
  const outcome = record.outcome;
  if (outcome === null) {
    return null;
  }
  switch (outcome.kind) {
    case "value":
      return outcome.display === null
        ? null
        : valueOutput(record, outcome.display);
    case "error":
      return errorOutput(record, [cellError(outcome.error)]);
    case "interrupted":
      return errorOutput(record, [{ type: "interruption" }]);
    case "skipped":
      return skippedOutput(record, outcome);
  }
}

/**
 * What a cell shows: its running value so far, else its result's outcome.
 *
 * A running execution's outcome is null until it shows something, so the
 * result stays up until then. Once it has shown, an empty display means
 * the cell cleared its output, and nothing shows.
 */
export function cellOutputView(
  inputs: CellOutputInputs,
  id: Protocol.CellId,
): CellOutput | null {
  const latestId = inputs.executions.latest.get(id);
  const latest =
    latestId === undefined
      ? undefined
      : inputs.executions.executions.get(latestId)?.record;
  if (latest !== undefined && latest.outcome !== null) {
    if (latest.status !== "completed") {
      return outcomeOutput(latest, inputs.cells);
    }
  }
  const result = inputs.results.get(id);
  if (result === null || result === undefined) {
    return null;
  }
  if (inputs.cleared.get(id) === result.id) {
    return null;
  }
  return outcomeOutput(result, inputs.cells);
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
      outputs.set(brand(cellId), output);
    }
  }
  return outputs;
}

/** What the scratchpad shows, from its latest scratch execution. */
export function scratchOutputView(executions: Executions): CellOutput | null {
  let scratch: Protocol.Execution | undefined;
  for (const { record } of executions.executions.values()) {
    if (record.cell_id !== null) {
      continue;
    }
    if (
      scratch === undefined ||
      seconds(record.started_at) >= seconds(scratch.started_at)
    ) {
      scratch = record;
    }
  }
  if (scratch === undefined) {
    return null;
  }
  return outcomeOutput(scratch);
}
