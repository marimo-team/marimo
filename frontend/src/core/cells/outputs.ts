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
// Outputs only fall back to this map where their `expand_output` config cannot
// be edited; see `useExpandedOutput`.
const expandedOutputs: Record<CellId, boolean> = {};

/**
 * Whether a cell's output is shown in full, instead of clamped to a fixed
 * height. A cell's output area and console output area share this one flag, so
 * expanding either expands both.
 *
 * In edit mode this is backed by the cell's `expand_output` config, so the
 * choice is saved to the notebook file and restored when it is reopened.
 * Cell configs are read-only in other modes, so the toggle is instead kept in
 * memory for the lifetime of the page.
 */
export function useExpandedOutput(cellId: CellId) {
  const { mode } = useAtomValue(viewStateAtom);
  const { updateCellConfig } = useCellActions();
  // Select just the flag: every output would otherwise re-render on each
  // keystroke in its cell.
  const configState = useAtomValue(
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
  const [sessionState, setSessionState] = useState(
    () => expandedOutputs[cellId] ?? configState,
  );

  // Sync state to external storage
  useEffect(() => {
    expandedOutputs[cellId] = sessionState;
  }, [cellId, sessionState]);

  const isEditable = mode === "edit";
  const isExpanded = isEditable ? configState : sessionState;

  const setIsExpanded = useEvent((expanded: boolean) => {
    if (!isEditable) {
      setSessionState(expanded);
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
