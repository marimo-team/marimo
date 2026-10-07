/* Copyright 2026 Marimo. All rights reserved. */

import type { OutputMessage } from "@/core/kernel/messages";
import { isConnectedAtom } from "@/core/network/connection";
import type { JotaiStore } from "@/core/state/jotai";
import { getMimeBundleEntries, processMimeBundle } from "@/utils/mime-types";
import { outputIsLoading } from "./cell";
import { notebookAtom } from "./cells";
import type { CellId } from "./ids";
import { isOutputEmpty } from "./outputs";
import type { CellRuntimeState } from "./types";

type OutputState = "unknown" | "pending" | "empty" | "available";
type CaptureState = Exclude<OutputState, "available"> | "ready" | "missing";

interface CaptureInterface {
  getCellState(cellId: string): CaptureState;
}

declare global {
  interface Window {
    __marimoCapture?: CaptureInterface;
  }
}

// Weak keys release removed output elements without a separate cleanup registry.
const committedOutputs = new WeakMap<Element, OutputMessage>();

export function getCellOutputState(
  runtime: CellRuntimeState | undefined,
): OutputState {
  if (!runtime) {
    return "unknown";
  }
  const loading = outputIsLoading(runtime.status);
  const freshProgress =
    runtime.status === "running" &&
    runtime.runStartTimestamp !== null &&
    (runtime.output?.timestamp ?? 0) > runtime.runStartTimestamp;
  if (loading && !freshProgress) {
    return "pending";
  }
  if (runtime.output?.mimetype === "application/vnd.marimo+mimebundle") {
    let data: unknown = runtime.output.data;
    if (typeof data === "string") {
      try {
        data = JSON.parse(data);
      } catch {
        // Malformed data is an output-rendering error, not an empty bundle.
        return "available";
      }
    }
    const bundle = Array.isArray(data) ? data[0] : data;
    if (
      bundle !== null &&
      typeof bundle === "object" &&
      processMimeBundle(getMimeBundleEntries(bundle as Record<string, unknown>))
        .entries.length === 0
    ) {
      return loading ? "pending" : "empty";
    }
  }
  if (!isOutputEmpty(runtime.output)) {
    return "available";
  }
  if (loading) {
    return "pending";
  }
  return runtime.output === null ? "unknown" : "empty";
}

/** Installed once; queries read live state only for the requested cell. */
export function installCaptureInterface(store: JotaiStore): void {
  window.__marimoCapture = {
    getCellState(cellId) {
      const notebook = store.get(notebookAtom);
      const id = cellId as CellId;
      if (!notebook.cellData[id]) {
        return "missing";
      }
      const runtime = notebook.cellRuntime[id];
      if (!runtime) {
        return "unknown";
      }
      if (!store.get(isConnectedAtom)) {
        return "unknown";
      }
      const state = getCellOutputState(runtime);
      if (state !== "available") {
        return state;
      }
      const element = document.getElementById(`output-${cellId}`);
      if (
        !element ||
        committedOutputs.get(element) !== runtime.output ||
        element.getClientRects().length === 0 ||
        (element.children.length === 0 && !element.textContent?.trim())
      ) {
        return "pending";
      }
      return "ready";
    },
  };
}

/** Ref callbacks run during commit, after child DOM mutations. */
export function getCaptureOutputRef(output: OutputMessage) {
  if (!window.__marimoCapture) {
    return undefined;
  }
  return (element: HTMLDivElement | null) => {
    if (element) {
      committedOutputs.set(element, output);
    }
  };
}
