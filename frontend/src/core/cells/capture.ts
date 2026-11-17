/* Copyright 2026 Marimo. All rights reserved. */

import {
  type CellExecutionView,
  type CellOutput,
  cellExecutionInputsAtom,
  cellExecutionView,
  cellOutputInputsAtom,
  cellOutputView,
} from "@/core/executions";
import { isConnectedAtom } from "@/core/network/connection";
import type { JotaiStore } from "@/core/state/jotai";
import { getMimeBundleEntries, processMimeBundle } from "@/utils/mime-types";
import { outputIsLoading } from "./cell";
import { notebookAtom } from "./cells";
import type { CellId } from "./ids";
import { isOutputEmpty } from "./outputs";

type OutputState = "unknown" | "pending" | "empty" | "available";

interface CaptureInterface {
  getCellState(cellId: string): OutputState | "missing";
}

declare global {
  interface Window {
    __marimoCapture?: CaptureInterface;
  }
}

export function getCellOutputState(
  output: CellOutput | null,
  execution: Pick<CellExecutionView, "status" | "rendered" | "outcome">,
): OutputState {
  const loading = outputIsLoading(execution.status);
  if (loading && !execution.rendered) {
    return "pending";
  }
  if (output?.mimetype === "application/vnd.marimo+mimebundle") {
    let data: unknown = output.data;
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
  if (!isOutputEmpty(output)) {
    return "available";
  }
  if (loading) {
    return "pending";
  }
  return output === null && execution.outcome === null ? "unknown" : "empty";
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
      if (!store.get(isConnectedAtom)) {
        return "unknown";
      }
      return getCellOutputState(
        cellOutputView(store.get(cellOutputInputsAtom), id),
        cellExecutionView(store.get(cellExecutionInputsAtom), id),
      );
    },
  };
}
