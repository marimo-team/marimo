/* Copyright 2026 Marimo. All rights reserved. */

/** Reads of an execution's state that hold whatever its status is. */

import type * as Protocol from "@marimo-team/client/protocol";

/** What an execution shows in place of a cell's output. */
export type Shown =
  | { readonly kind: "output"; readonly media: Protocol.Media | null }
  | Exclude<Protocol.ExecutionOutcomeOutput, { kind: "succeeded" }>;

/**
 * How an execution ended when it did not succeed, else its output. Null
 * until a queued or running execution sets its output.
 */
export function shown(result: {
  readonly record: Protocol.ExecutionOutput;
  readonly output: Protocol.Output | null;
}): Shown | null {
  const { state } = result.record;
  if (state.status === "completed" && state.outcome.kind !== "succeeded") {
    return state.outcome;
  }
  if (result.output !== null) {
    return { kind: "output", media: result.output.media };
  }
  return state.status === "completed" ? { kind: "output", media: null } : null;
}

export function startedAt(record: Protocol.Execution): string | null {
  return record.state.status === "queued" ? null : record.state.started_at;
}

export function completedAt(record: Protocol.Execution): string | null {
  return record.state.status === "completed" ? record.state.completed_at : null;
}

/** The revisions a completed execution read. Empty until it completes. */
export function dependsOn(
  record: Protocol.Execution,
): Protocol.ExecutionCompleted["depends_on"] {
  return record.state.status === "completed" ? record.state.depends_on : {};
}
