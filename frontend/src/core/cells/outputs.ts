/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useState } from "react";
import type { OutputMessage } from "../kernel/messages";
import type { CellId } from "./ids";

// This does not need to be overcomplicated. We can just store the expanded
// state in a global map instead of Jotai since state is not shared between cells.
const expandedOutputs: Record<CellId, boolean> = {};
const expandedConsoleOutputs: Record<CellId, boolean> = {};

export function useExpandedOutput(cellId: CellId) {
  const [state, setState] = useState(expandedOutputs[cellId] ?? false);

  // Sync state to external storage
  useEffect(() => {
    expandedOutputs[cellId] = state;
  }, [cellId, state]);

  return [state, setState] as const;
}

export function useExpandedConsoleOutput(cellId: CellId) {
  const [state, setState] = useState(expandedConsoleOutputs[cellId] ?? false);

  // Sync state to external storage
  useEffect(() => {
    expandedConsoleOutputs[cellId] = state;
  }, [cellId, state]);

  return [state, setState] as const;
}

export function isOutputEmpty(
  output: OutputMessage | undefined | null,
): boolean {
  if (output == null) {
    return true;
  }

  if (output.data == null || output.data === "") {
    return true;
  }

  return false;
}
