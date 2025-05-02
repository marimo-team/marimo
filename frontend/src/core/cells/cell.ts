/* Copyright 2024 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import type { CellMessage, OutputMessage } from "../kernel/messages";
import type { CellRuntimeState } from "./types";
import { collapseConsoleOutputs } from "./collapseConsoleOutputs";
import { parseOutline } from "../dom/outline";
import { type Seconds, Time } from "@/utils/time";
import { invariant } from "@/utils/invariant";
import type { RuntimeState } from "../network/types";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";

export function transitionCell(
  cell: CellRuntimeState,
  message: CellMessage,
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
      // Clear interrupted here in case we start as "running"
      // This can happen on a resumed session
      nextCell.interrupted = false;
      // If was previously stopped, clear the outputs
      if (cell.stopped) {
        nextCell.output = null;
      }
      // If it transitioned from queued to running, remove previous console outputs
      if (nextCell.status === "queued") {
        nextCell.consoleOutputs = [];
      }
      nextCell.stopped = false;
      nextCell.runStartTimestamp = message.timestamp as Seconds;
      // Store the last run timestamp, since this gets cleared once idle
      nextCell.lastRunStartTimestamp = message.timestamp as Seconds;
      break;
    case "idle":
      if (cell.runStartTimestamp) {
        nextCell.runElapsedTimeMs = Time.fromSeconds(
          (message.timestamp - cell.runStartTimestamp) as Seconds,
        ).toMilliseconds();
        nextCell.runStartTimestamp = null;
        nextCell.staleInputs = false;
      }
      // If last run start timestamp is not set, set it to the current timestamp
      // This happens on a resumed session
      if (!cell.lastRunStartTimestamp && message.timestamp) {
        nextCell.lastRunStartTimestamp = message.timestamp as Seconds;
      }
      nextCell.debuggerActive = false;
      break;
    case null:
      break;
    case "disabled-transitively":
      // Everything should already be up to date from prepareCellForExecution
      break;
    case undefined:
      break;
    default:
      logNever(message.status);
  }

  nextCell.output = message.output ?? nextCell.output;
  nextCell.staleInputs = message.stale_inputs ?? nextCell.staleInputs;
  nextCell.status = message.status ?? nextCell.status;
  nextCell.serialization = message.serialization;

  let didInterruptFromThisMessage = false;

  // Handle errors: marimo includes an error output when a cell is interrupted
  // or errored
  if (
    message.output != null &&
    message.output.mimetype === "application/vnd.marimo+error"
  ) {
    // The frontend manually sets status to queued when a user runs a cell,
    // to give immediate feedback, but the kernel doesn't know that.
    //
    // TODO(akshayka): Move all status management to the backend.
    if (nextCell.status === "queued" || nextCell.status === "running") {
      nextCell.status = "idle";
    }

    invariant(
      Array.isArray(message.output.data),
      "Expected error output data to be an array",
    );
    if (message.output.data.some((error) => error.type === "interruption")) {
      // Interrupted helps distinguish that the cell is stale
      nextCell.interrupted = true;
      didInterruptFromThisMessage = true;
    } else if (
      message.output.data.some((error) => error.type.includes("ancestor"))
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

  // If interrupted on the incoming message,
  // remove the debugger and resolve all stdin for previous console outputs
  if (didInterruptFromThisMessage) {
    nextCell.debuggerActive = false;
    consoleOutputs = consoleOutputs.map((output) => {
      if (output.channel === "stdin") {
        return { ...output, response: output.response ?? "" };
      }
      return output;
    });
  }

  if (message.console !== null) {
    // The kernel sends an empty array to clear the console; otherwise,
    // message.console is an output that needs to be appended to the
    // existing console outputs.
    consoleOutputs = Array.isArray(message.console)
      ? message.console
      : collapseConsoleOutputs(
          [...consoleOutputs, message.console].filter(Boolean),
        );
  }
  nextCell.consoleOutputs = consoleOutputs;
  // Derive outline from output
  nextCell.outline = parseOutline(nextCell.output);

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

// Should be called when a cell's code is registered with the kernel for
// execution.
export function prepareCellForExecution(
  cell: CellRuntimeState,
): CellRuntimeState {
  const nextCell = { ...cell };

  if (cell.status !== "disabled-transitively") {
    // TODO(akshayka): Move this to the backend. It's in the FE right now
    // to give the user immediate feedback.
    nextCell.status = "queued";
  }
  nextCell.interrupted = false;
  nextCell.errored = false;
  nextCell.runElapsedTimeMs = null;
  nextCell.debuggerActive = false;

  return nextCell;
}

/**
 * A cell's output is loading if it is running or queued.
 */
export function outputIsLoading(status: RuntimeState): boolean {
  return status === "running" || status === "queued";
}

/**
 * A cell's output is stale if it has been edited, is loading, or has errored.
 */
export function outputIsStale(
  cell: Pick<
    CellRuntimeState,
    "status" | "output" | "runStartTimestamp" | "interrupted" | "staleInputs"
  >,
  edited: boolean,
): boolean {
  const { status, output, runStartTimestamp, interrupted, staleInputs } = cell;

  // If interrupted, the output is not stale
  if (interrupted) {
    return false;
  }

  // If edited, the cell's output is stale
  if (edited) {
    return true;
  }

  // The cell is loading
  const loading = outputIsLoading(status);

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

  return staleInputs;
}

/**
 * Convert a list of outputs to a traceback info.
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
