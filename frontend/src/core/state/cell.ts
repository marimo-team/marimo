/* Copyright 2023 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import { CellMessage } from "../kernel/messages";
import { CellState } from "../model/cells";
import { collapseConsoleOutputs } from "../model/collapseConsoleOutputs";

export function transitionCell(
  cell: CellState,
  message: CellMessage
): CellState {
  const nextCell = { ...cell };

  // Handle status transition and update output; message.status !== null
  // implies a status transition
  switch (message.status) {
    case "queued":
      nextCell.stopped = false;
      nextCell.interrupted = false;
      nextCell.errored = false;
      // We intentionally don't update lastCodeRun, since the kernel queues
      // whatever code was last registered with it, which might not match
      // the cell's current code if the user modified it.
      break;
    case "running":
      nextCell.runStartTimestamp = message.timestamp;
      break;
    case "idle":
      nextCell.output = message.output;
      if (cell.runStartTimestamp) {
        nextCell.runElapsedTimeMs =
          (message.timestamp - cell.runStartTimestamp) * 1000;
        nextCell.runStartTimestamp = null;
      }
      break;
    case null:
      break;
    case "stale":
      // Everything should already be up to date from prepareCellForExecution
      break;
    default:
      logNever(message.status);
  }
  nextCell.status = message.status ?? cell.status;

  // Handle errors: marimo includes an error output when a cell is interrupted
  // or errored
  if (
    message.output !== null &&
    message.output.mimetype === "application/vnd.marimo+error"
  ) {
    if (message.output.data.some((error) => error["type"] === "interruption")) {
      // This cell needs to be re-run, even if its code contents haven't
      // changed since it was last run. Force the re-run state by clearing
      // its lastCodeRun
      nextCell.lastCodeRun = null;
      nextCell.interrupted = true;
    } else if (
      message.output.data.some((error) => error["type"] === "ancestor-stopped")
    ) {
      // The cell didn't run, but it was intentional, so don't count as
      // errored.
      nextCell.stopped = true;
      nextCell.runElapsedTimeMs = null;
    } else {
      nextCell.errored = true;
      // The cell didn't actually run.
      nextCell.runElapsedTimeMs = null;
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
  return nextCell;
}

// Should be called when a cell's code is registered with the kernel for
// execution.
export function prepareCellForExecution(cell: CellState): CellState {
  const nextCell = { ...cell };

  nextCell.interrupted = false;
  nextCell.errored = false;
  nextCell.edited = false;
  nextCell.runElapsedTimeMs = null;
  nextCell.lastCodeRun = cell.code.trim();

  return nextCell;
}
