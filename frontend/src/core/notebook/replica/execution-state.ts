/* Copyright 2026 Marimo. All rights reserved. */

/** Reads of an execution's state that hold whatever its status is. */

import type * as Protocol from "@marimo-team/client/protocol";

/** The final outcome once completed, or the value so far while running. */
export function shownOutcome(
  record: Protocol.Execution,
): Protocol.Outcome | null {
  const state = record.state;
  switch (state.status) {
    case "queued":
      return null;
    case "running":
      return state.value;
    case "completed":
      return state.outcome;
  }
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
