/* Copyright 2026 Marimo. All rights reserved. */

import type { Milliseconds, Seconds } from "@/utils/time";
import type { CellData, CellRuntimeState } from "./types";

export type CellExecutionPhase =
  | { kind: "idle" }
  | { kind: "queued" }
  | { kind: "running"; startedAt: Seconds | null };

export type CellAvailability =
  | { kind: "enabled" }
  | { kind: "paused" }
  | { kind: "blocked"; reason: "disabled-ancestor" };

export type CellFreshness =
  | { kind: "not-run" }
  | { kind: "current" }
  | {
      kind: "outdated";
      reasons: Array<"code-edited" | "inputs-changed">;
    };

export type CellLastRunOutcome =
  | { kind: "none" }
  | { kind: "success"; elapsed: Milliseconds | null }
  | { kind: "interrupted"; elapsed: Milliseconds | null }
  | { kind: "stopped"; elapsed: Milliseconds | null }
  | { kind: "failed"; elapsed: Milliseconds | null };

export type CellOutputState = "current" | "previous" | "updating";

export function deriveOutputStateFromFlags(
  stale: boolean,
  loading: boolean,
): CellOutputState {
  if (!stale) {
    return "current";
  }
  return loading ? "updating" : "previous";
}

export function deriveMainOutputState(
  edited: boolean,
  runtime: Pick<
    CellRuntimeState,
    "status" | "output" | "staleInputs" | "interrupted" | "runStartTimestamp"
  >,
): CellOutputState {
  if (runtime.interrupted) {
    return "current";
  }

  const outputFromCurrentRun =
    runtime.status === "running" &&
    runtime.output !== null &&
    runtime.runStartTimestamp !== null &&
    (runtime.output.timestamp ?? 0) > runtime.runStartTimestamp;

  if (
    (runtime.status === "running" || runtime.status === "queued") &&
    !outputFromCurrentRun
  ) {
    return "updating";
  }
  if (edited || runtime.staleInputs) {
    return "previous";
  }
  return "current";
}

/**
 * The normalized, semantic state consumed by cell UI. Runtime fields are
 * intentionally interpreted here so individual components cannot invent
 * conflicting precedence rules.
 */
export interface CellSemanticState {
  phase: CellExecutionPhase;
  availability: CellAvailability;
  freshness: CellFreshness;
  lastRun: CellLastRunOutcome;
  mainOutput: CellOutputState;
  consoleOutput: CellOutputState;
  codeEdited: boolean;
  inputsChanged: boolean;
  /** Whether the idle UI should invite the user to run this cell. */
  needsRun: boolean;
  /** Whether a global run action should schedule or synchronize this cell. */
  shouldSchedule: boolean;
  lastRunStartedAt: Seconds | null;
}

export interface CellStateSummary {
  running: number;
  queued: number;
  pending: number;
  unavailableOutdated: number;
  failed: number;
}

export function summarizeCellStates(
  states: readonly CellSemanticState[],
): CellStateSummary {
  return states.reduce<CellStateSummary>(
    (summary, state) => ({
      running: summary.running + Number(state.phase.kind === "running"),
      queued: summary.queued + Number(state.phase.kind === "queued"),
      pending:
        summary.pending +
        Number(state.needsRun && state.availability.kind === "enabled"),
      unavailableOutdated:
        summary.unavailableOutdated +
        Number(
          state.freshness.kind === "outdated" &&
            state.availability.kind !== "enabled",
        ),
      failed: summary.failed + Number(state.lastRun.kind === "failed"),
    }),
    {
      running: 0,
      queued: 0,
      pending: 0,
      unavailableOutdated: 0,
      failed: 0,
    },
  );
}

export function deriveCellSemanticState(
  cellData: Pick<CellData, "edited" | "lastExecutionTime" | "config">,
  runtime: Pick<
    CellRuntimeState,
    | "status"
    | "output"
    | "staleInputs"
    | "interrupted"
    | "errored"
    | "stopped"
    | "runElapsedTimeMs"
    | "runStartTimestamp"
    | "lastRunStartTimestamp"
  >,
): CellSemanticState {
  const phase: CellExecutionPhase =
    runtime.status === "running"
      ? { kind: "running", startedAt: runtime.runStartTimestamp }
      : runtime.status === "queued"
        ? { kind: "queued" }
        : { kind: "idle" };

  const availability: CellAvailability = cellData.config.disabled
    ? { kind: "paused" }
    : runtime.status === "disabled-transitively"
      ? { kind: "blocked", reason: "disabled-ancestor" }
      : { kind: "enabled" };

  const executionTime = (runtime.runElapsedTimeMs ??
    cellData.lastExecutionTime) as Milliseconds | null;
  const notRun =
    executionTime === null &&
    phase.kind === "idle" &&
    !runtime.errored &&
    !runtime.interrupted &&
    !runtime.stopped;

  const outdatedReasons: Extract<
    CellFreshness,
    { kind: "outdated" }
  >["reasons"] = [];
  if (cellData.edited) {
    outdatedReasons.push("code-edited");
  }
  if (runtime.staleInputs) {
    outdatedReasons.push("inputs-changed");
  }

  const freshness: CellFreshness = notRun
    ? { kind: "not-run" }
    : outdatedReasons.length > 0
      ? { kind: "outdated", reasons: outdatedReasons }
      : { kind: "current" };

  const lastRun: CellLastRunOutcome = runtime.errored
    ? { kind: "failed", elapsed: executionTime }
    : runtime.interrupted
      ? { kind: "interrupted", elapsed: executionTime }
      : runtime.stopped
        ? { kind: "stopped", elapsed: executionTime }
        : executionTime !== null
          ? { kind: "success", elapsed: executionTime }
          : { kind: "none" };

  const mainOutput = deriveMainOutputState(cellData.edited, runtime);

  let consoleOutput: CellOutputState = "current";
  if (!runtime.interrupted) {
    if (phase.kind === "queued") {
      consoleOutput = "updating";
    } else if (cellData.edited || runtime.staleInputs) {
      consoleOutput = "previous";
    }
  }

  // Edited code must still be synchronized for paused and blocked cells. Input
  // changes alone are not actionable until those cells become available.
  const shouldSchedule =
    (freshness.kind === "not-run" && availability.kind !== "blocked") ||
    cellData.edited ||
    runtime.interrupted ||
    (runtime.staleInputs && availability.kind === "enabled");
  const needsRun = phase.kind === "idle" && shouldSchedule;

  return {
    phase,
    availability,
    freshness,
    lastRun,
    mainOutput,
    consoleOutput,
    codeEdited: cellData.edited,
    inputsChanged: runtime.staleInputs,
    needsRun,
    shouldSchedule,
    lastRunStartedAt:
      runtime.runStartTimestamp ?? runtime.lastRunStartTimestamp,
  };
}

export type CellEmphasis = "none" | "active" | "failed";

export type CellStatusPrimary =
  | "running"
  | "queued"
  | "paused"
  | "blocked"
  | "error"
  | "interrupted"
  | "stopped"
  | "not-run"
  | "outdated"
  | "current";

export interface CellStatusPresentation {
  primary: CellStatusPrimary;
  modifiers: {
    outdated: boolean;
    hasError: boolean;
  };
  kind: string;
  label: string;
  description: string;
  tone: "active" | "danger" | "muted" | "neutral";
}

export interface CellPresentation {
  emphasis: CellEmphasis;
  showPrimaryAction: boolean;
  accessibleLabel: string;
}

export function presentCellStatus(
  state: CellSemanticState,
): CellStatusPresentation {
  const outdated = state.freshness.kind === "outdated";
  const hasError = state.lastRun.kind === "failed";

  const primary: CellStatusPrimary =
    state.phase.kind === "running"
      ? "running"
      : state.phase.kind === "queued"
        ? "queued"
        : state.availability.kind === "paused"
          ? "paused"
          : state.availability.kind === "blocked"
            ? "blocked"
            : hasError
              ? "error"
              : state.lastRun.kind === "interrupted"
                ? "interrupted"
                : state.lastRun.kind === "stopped"
                  ? "stopped"
                  : state.freshness.kind === "not-run"
                    ? "not-run"
                    : outdated
                      ? "outdated"
                      : "current";

  const base = {
    running: {
      label: "Running",
      description: "This cell is running.",
    },
    queued: {
      label: "Queued",
      description: "This cell is queued to run.",
    },
    paused: {
      label: "Paused",
      description: "Execution is paused for this cell.",
    },
    blocked: {
      label: "Blocked",
      description: "A paused upstream cell is blocking this cell.",
    },
    error: {
      label: "Error",
      description: "This cell has an error.",
    },
    interrupted: {
      label: "Interrupted",
      description: "This cell was interrupted and can be run again.",
    },
    stopped: {
      label: "Stopped upstream",
      description: "This cell did not run because an upstream cell stopped.",
    },
    "not-run": {
      label: "Not run",
      description: "This cell has not been run.",
    },
    outdated: {
      label: "Outdated",
      description: "This cell has not run with its current code or inputs.",
    },
    current: {
      label: "Current",
      description: "This cell is up to date.",
    },
  } satisfies Record<CellStatusPrimary, { label: string; description: string }>;

  const showModifiers = primary === "paused" || primary === "blocked";
  const labels = [base[primary].label];
  const descriptions = [base[primary].description];

  if (
    (showModifiers || primary === "error") &&
    hasError &&
    primary !== "error"
  ) {
    labels.push("Error");
    descriptions.push("This cell also has an error.");
  }
  if ((showModifiers || primary === "error") && outdated) {
    labels.push("Outdated");
    descriptions.push(
      state.codeEdited
        ? "Its code has changed and needs to run."
        : "Its inputs have changed and it needs to run.",
    );
  }

  return {
    primary,
    modifiers: { outdated, hasError },
    kind: [
      primary,
      hasError && primary !== "error" ? "error" : null,
      outdated && primary !== "outdated" ? "outdated" : null,
    ]
      .filter(Boolean)
      .join("-"),
    label: labels.join(" · "),
    description: descriptions.join(" "),
    tone:
      primary === "running" || primary === "queued"
        ? "active"
        : hasError
          ? "danger"
          : primary === "outdated"
            ? "neutral"
            : "muted",
  };
}

export function presentCellState(state: CellSemanticState): CellPresentation {
  const status = presentCellStatus(state);
  if (state.phase.kind === "running") {
    return {
      emphasis: "active",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.phase.kind === "queued") {
    return {
      emphasis: "active",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.availability.kind === "paused") {
    return {
      emphasis: status.modifiers.hasError ? "failed" : "none",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.availability.kind === "blocked") {
    return {
      emphasis: status.modifiers.hasError ? "failed" : "none",
      showPrimaryAction: state.codeEdited,
      accessibleLabel: status.description,
    };
  }
  if (state.lastRun.kind === "failed") {
    return {
      emphasis: "failed",
      showPrimaryAction: state.needsRun,
      accessibleLabel: status.description,
    };
  }
  if (state.lastRun.kind === "interrupted") {
    return {
      emphasis: "none",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.lastRun.kind === "stopped") {
    return {
      emphasis: "none",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.freshness.kind === "not-run") {
    return {
      emphasis: "none",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  if (state.freshness.kind === "outdated") {
    return {
      emphasis: "none",
      showPrimaryAction: true,
      accessibleLabel: status.description,
    };
  }
  return {
    emphasis: "none",
    showPrimaryAction: false,
    accessibleLabel: status.description,
  };
}

export function cellStateDataAttributes(state: CellSemanticState) {
  return {
    "data-cell-phase": state.phase.kind,
    "data-cell-availability": state.availability.kind,
    "data-cell-freshness": state.freshness.kind,
    "data-cell-outcome": state.lastRun.kind,
    "data-cell-code-edited": state.codeEdited,
    "data-cell-inputs-changed": state.inputsChanged,
  } as const;
}
