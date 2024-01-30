/* Copyright 2024 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import { CellMessage, OutputMessage } from "../kernel/messages";
import { CellRuntimeState } from "./types";
import { collapseConsoleOutputs } from "./collapseConsoleOutputs";
import { parseOutline } from "../dom/outline";
import { Seconds, Time } from "@/utils/time";

export function transitionCell(
  cell: CellRuntimeState,
  message: CellMessage
): CellRuntimeState {
  const nextCell = { ...cell };

  // Handle status transition and update output; message.status !== null
  // implies a status transition
  switch (message.status) {
    case "queued":
      nextCell.interrupted = false;
      nextCell.errored = false;
      nextCell.runElapsedTimeMs = null;
      nextCell.debuggerActive = false;
      // We intentionally don't update lastCodeRun, since the kernel queues
      // whatever code was last registered with it, which might not match
      // the cell's current code if the user modified it.
      break;
    case "running":
      // If was previously stopped, clear the outputs
      if (cell.stopped) {
        nextCell.output = null;
      }
      // If it transitioned from queued to running, remove previous console outputs
      if (nextCell.status === "queued") {
        nextCell.consoleOutputs = [];
      }
      nextCell.stopped = false;
      nextCell.runStartTimestamp = message.timestamp;
      break;
    case "idle":
      if (cell.runStartTimestamp) {
        nextCell.runElapsedTimeMs = Time.fromSeconds(
          (message.timestamp - cell.runStartTimestamp) as Seconds
        ).toMilliseconds();
        nextCell.runStartTimestamp = null;
      }
      nextCell.debuggerActive = false;
      break;
    case null:
      break;
    case "stale":
      // Everything should already be up to date from prepareCellForExecution
      break;
    case "disabled-transitively":
      // Everything should already be up to date from prepareCellForExecution
      break;
    default:
      logNever(message.status);
  }

  nextCell.output = message.output ?? nextCell.output;
  nextCell.status = message.status ?? nextCell.status;

  // Handle errors: marimo includes an error output when a cell is interrupted
  // or errored
  if (
    message.output !== null &&
    message.output.mimetype === "application/vnd.marimo+error"
  ) {
    if (message.output.data.some((error) => error.type === "interruption")) {
      // Interrupted helps distinguish that the cell is stale
      nextCell.interrupted = true;
    } else if (
      message.output.data.some((error) => error.type === "ancestor-stopped")
    ) {
      // The cell didn't run, but it was intentional, so don't count as
      // errored.
      nextCell.stopped = true;
    } else {
      // Communicate that the cell errored (e.g., an exception was raised)
      nextCell.errored = true;
    }
  }

  // Coalesce console outputs, which are streamed during execution.
  let consoleOutputs = cell.consoleOutputs;
  if (message.console !== null) {
    // The kernel sends an empty array to clear the console; otherwise,
    // message.console is an output that needs to be appended to the
    // existing console outputs.
    consoleOutputs = Array.isArray(message.console)
      ? message.console
      : collapseConsoleOutputs([...cell.consoleOutputs, message.console]);
  }
  nextCell.consoleOutputs = consoleOutputs;
  // Derive outline from output
  nextCell.outline = parseOutline(nextCell.output);

  // Transition PDB
  const newConsoleOutputs = [message.console].flat().filter(Boolean);
  const pdbOutputs = newConsoleOutputs.filter(
    (output): output is Extract<OutputMessage, { channel: "pdb" }> =>
      output.channel === "pdb"
  );
  const hasPdbOutput = pdbOutputs.length > 0;
  if (hasPdbOutput && pdbOutputs.some((output) => output.data === "start")) {
    nextCell.debuggerActive = true;
  }
  // If interrupted, remove the debugger and resolve all stdin
  if (nextCell.interrupted || nextCell.errored) {
    nextCell.debuggerActive = false;
    nextCell.consoleOutputs = nextCell.consoleOutputs.map((output) => {
      if (output.channel === "stdin") {
        return { ...output, response: output.response ?? "" };
      }
      return output;
    });
  }

  return nextCell;
}

// Should be called when a cell's code is registered with the kernel for
// execution.
export function prepareCellForExecution(
  cell: CellRuntimeState
): CellRuntimeState {
  const nextCell = { ...cell };

  nextCell.interrupted = false;
  nextCell.errored = false;
  nextCell.runElapsedTimeMs = null;
  nextCell.debuggerActive = false;

  return nextCell;
}

/**
 * A cell is stale if it has been edited, is loading, or has errored.
 */
export function outputIsStale(
  cell: Pick<
    CellRuntimeState,
    "status" | "output" | "runStartTimestamp" | "interrupted"
  >,
  edited: boolean
): boolean {
  const { status, output, runStartTimestamp, interrupted } = cell;

  // If interrupted, the cell is not stale
  if (interrupted) {
    return false;
  }

  // If edited, the cell is stale
  if (edited) {
    return true;
  }

  // The cell is loading
  const loading = status === "running" || status === "queued";

  // Output is received while the cell is running (e.g. mo.output.append())
  const outputReceivedWhileRunning =
    status === "running" &&
    output !== null &&
    runStartTimestamp !== null &&
    output.timestamp > runStartTimestamp;

  // If loading and output has not been received while running
  if (loading && !outputReceivedWhileRunning) {
    return true;
  }

  return status === "stale";
}
