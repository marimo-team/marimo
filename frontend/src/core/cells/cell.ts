/* Copyright 2026 Marimo. All rights reserved. */
import type {
  CellExecutionView,
  CellFreshness,
  CellRunStatus,
} from "@/core/executions";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";
import type { CellMessage, OutputMessage } from "../kernel/messages";
import { collapseConsoleOutputs } from "./collapseConsoleOutputs";
import type { CellRuntimeState, ConsoleOutputMessage } from "./types";

// Ids increase with position, so the last output holds the maximum.
function nextConsoleOutputId(outputs: ConsoleOutputMessage[]): number {
  return (outputs.at(-1)?.id ?? 0) + 1;
}

function errorTypes(output: OutputMessage | null | undefined): string[] {
  if (
    output == null ||
    output.mimetype !== "application/vnd.marimo+error" ||
    !Array.isArray(output.data)
  ) {
    return [];
  }
  return output.data.map((error) => error.type);
}

export function transitionCell(
  cell: CellRuntimeState,
  message: CellMessage,
): CellRuntimeState {
  const nextCell = { ...cell };

  if (message.status === "queued") {
    nextCell.debuggerActive = false;
  }
  // Tri-state partial update: an omitted field (undefined) leaves the hint
  // unchanged; null explicitly clears it; a string sets it.
  if (message.serialization !== undefined) {
    nextCell.serialization = message.serialization;
  }

  const interrupted = errorTypes(message.output).includes("interruption");

  // Coalesce console outputs, which are streamed during execution.
  let consoleOutputs = cell.consoleOutputs;

  // When the cell is interrupted or finishes (idle), there is no live
  // stdin/pdb session, so resolve any dangling stdin prompt. This removes the
  // debugger box — e.g. after quitting pdb with `q`, which stops the cell
  // (idle) rather than interrupting it.
  if (interrupted || message.status === "idle") {
    nextCell.debuggerActive = false;
    consoleOutputs = consoleOutputs.map((output) => {
      if (output.channel === "stdin") {
        // StatefulOutputMessage exposes data through a getter, which object
        // spread would omit.
        return {
          channel: output.channel,
          mimetype: output.mimetype,
          data: output.data,
          timestamp: output.timestamp,
          id: output.id,
          input_id: output.input_id,
          response: output.response ?? "",
        };
      }
      return output;
    });
  }

  const messageConsole = message.console;
  if (messageConsole != null) {
    // The kernel sends an empty array to clear the console; otherwise,
    // messageConsole is an output that needs to be appended to the
    // existing console outputs.
    consoleOutputs = Array.isArray(messageConsole)
      ? collapseConsoleOutputs(
          messageConsole.map((output, i) => ({ ...output, id: i + 1 })),
        )
      : collapseConsoleOutputs([
          ...consoleOutputs,
          { ...messageConsole, id: nextConsoleOutputId(consoleOutputs) },
        ]);
  }
  nextCell.consoleOutputs = consoleOutputs;

  // Transition PDB
  const newConsoleOutputs = [message.console].flat().filter(Boolean);
  const pdbOutputs = newConsoleOutputs.filter(
    (output) => output.channel === "pdb",
  );
  const hasPdbOutput = pdbOutputs.length > 0;
  if (hasPdbOutput && pdbOutputs.some((output) => output.data === "start")) {
    nextCell.debuggerActive = true;
  }

  return nextCell;
}

/**
 * A cell's output is loading if it is running or queued.
 */
export function outputIsLoading(status: CellRunStatus): boolean {
  return status === "running" || status === "queued";
}

/**
 * A cell's output is stale if it is loading, an input it read has changed,
 * or, while `editing`, its source has changed. A read view keeps showing
 * the last result of edited source.
 */
export function outputIsStale(
  execution: Pick<CellExecutionView, "status" | "outcome" | "rendered">,
  freshness: CellFreshness,
  editing: boolean,
): boolean {
  const { status, outcome, rendered } = execution;

  // A run in progress owns the output area: loading until the running cell
  // has shown output (e.g. mo.output.append()), whatever the last result was.
  if (outputIsLoading(status)) {
    return !(status === "running" && rendered);
  }
  if (editing && freshness.sourceChanged) {
    return true;
  }
  // An interrupted run's partial output stands as the record of that run.
  if (outcome === "interrupted") {
    return false;
  }
  return freshness.inputsChanged;
}

/**
 * Console output is stale while a run is queued, since the run will clear
 * it, and once a settled result is outdated. A run in progress owns it.
 */
export function consoleOutputIsStale(
  execution: Pick<CellExecutionView, "status" | "outcome">,
  freshness: CellFreshness,
): boolean {
  const { status, outcome } = execution;
  if (outcome === "interrupted") {
    return false;
  }
  if (status === "queued") {
    return true;
  }
  if (status === "running") {
    return false;
  }
  return freshness.sourceChanged || freshness.inputsChanged;
}

/**
 * Extract traceback information from a list of outputs.
 * This function searches for the first output with a mimetype of
 * "application/vnd.marimo+traceback" and parses its data to retrieve
 * all traceback details.
 */
export function outputToTracebackInfo(
  outputs: OutputMessage[],
): TracebackInfo[] | undefined {
  const firstTraceback = outputs.find(
    (output) => output.mimetype === "application/vnd.marimo+traceback",
  );
  if (!firstTraceback) {
    return undefined;
  }
  const traceback = firstTraceback.data;
  if (typeof traceback !== "string") {
    return undefined;
  }
  return extractAllTracebackInfo(traceback);
}
