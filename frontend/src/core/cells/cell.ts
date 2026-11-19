/* Copyright 2026 Marimo. All rights reserved. */
import type {
  CellExecutionView,
  CellFreshness,
  CellRunStatus,
} from "@/core/executions";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";
import type { OutputMessage } from "../kernel/messages";
/**
 * A cell's output is loading if it is running or queued.
 */
export function outputIsLoading(status: CellRunStatus): boolean {
  return status === "running" || status === "queued";
}

/**
 * A settled output is stale if an input it read has changed,
 * or, while `editing`, its source has changed. A read view keeps showing
 * the last result of edited source.
 */
export function outputIsStale(
  execution: Pick<CellExecutionView, "status" | "outcome">,
  freshness: CellFreshness,
  editing: boolean,
): boolean {
  const { status, outcome } = execution;

  if (outputIsLoading(status)) {
    return false;
  }
  if (editing && freshness.sourceChanged) {
    return true;
  }
  // An interrupted run's partial output stands as the record of that run.
  if (outcome === "cancelled") {
    return false;
  }
  return freshness.inputsChanged;
}

/**
 * Console output is stale once its settled result is outdated.
 */
export function consoleOutputIsStale(
  execution: Pick<CellExecutionView, "status" | "outcome">,
  freshness: CellFreshness,
): boolean {
  const { status, outcome } = execution;
  if (outcome === "cancelled") {
    return false;
  }
  if (outputIsLoading(status)) {
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
