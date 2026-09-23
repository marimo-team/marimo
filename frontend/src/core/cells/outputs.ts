/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useEffect, useMemo, useState } from "react";
import { useEvent } from "@/hooks/useEvent";
import { Logger } from "@/utils/Logger";
import type { OutputMessage } from "../kernel/messages";
import { viewStateAtom } from "../mode";
import { getRequestClient } from "../network/requests";
import { cellDataAtom, useCellActions } from "./cells";
import type { CellId } from "./ids";

// This does not need to be overcomplicated. We can just store the expanded
// state in a global map instead of Jotai since state is not shared between cells.
// The output area only falls back to its map where the `expand_output` config
// cannot be edited; see `useExpandedOutput`.
const expandedOutputs: Record<CellId, boolean> = {};
const expandedConsoleOutputs: Record<CellId, boolean> = {};

/**
 * Whether a cell's output is shown in full, instead of clamped to a fixed
 * height. Covers the cell's output area only; console output is clamped
 * independently, via `useExpandedConsoleOutput`.
 *
 * In edit mode, we toggle the cell's `expand_output` config, so the choice is persisted.
 */
export function useExpandedOutput(cellId: CellId) {
  const { mode } = useAtomValue(viewStateAtom);
  const { updateCellConfig } = useCellActions();
  // Select just the flag: every output would otherwise re-render on each
  // keystroke in its cell.
  const isConfigExpanded = useAtomValue(
    useMemo(
      () =>
        selectAtom(
          cellDataAtom(cellId),
          (data) => data?.config.expand_output ?? false,
          Object.is,
        ),
      [cellId],
    ),
  );
  const [isSessionExpanded, setIsSessionExpanded] = useState(
    () => expandedOutputs[cellId] ?? isConfigExpanded,
  );

  // Sync state to external storage
  useEffect(() => {
    expandedOutputs[cellId] = isSessionExpanded;
  }, [cellId, isSessionExpanded]);

  const isEditable = mode === "edit";
  const isExpanded = isEditable ? isConfigExpanded : isSessionExpanded;

  const setIsExpanded = useEvent((expanded: boolean) => {
    setIsSessionExpanded(expanded);
    if (!isEditable) {
      return;
    }
    const config = { expand_output: expanded };
    updateCellConfig({ cellId, config });
    getRequestClient()
      .saveCellConfig({ configs: { [cellId]: config } })
      .catch((error) => {
        Logger.error("Failed to save expand_output config", error);
      });
  });

  return [isExpanded, setIsExpanded] as const;
}

/**
 * Whether a cell's console output is shown in full. Deliberately not backed by
 * `expand_output`: that config covers the cell's output area only, so console
 * output stays a per-session, in-memory toggle.
 */
export function useExpandedConsoleOutput(cellId: CellId) {
  const [isExpanded, setIsExpanded] = useState(
    expandedConsoleOutputs[cellId] ?? false,
  );

  // Sync state to external storage
  useEffect(() => {
    expandedConsoleOutputs[cellId] = isExpanded;
  }, [cellId, isExpanded]);

  return [isExpanded, setIsExpanded] as const;
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
