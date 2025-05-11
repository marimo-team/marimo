/* Copyright 2024 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { Logger } from "@/utils/Logger";
import type { CellId } from "@/core/cells/ids";
import {
  contextAwarePanelOpen,
  contextAwarePanelOwner,
  isCellAwareAtom,
} from "@/components/editor/chrome/panels/context-aware-panel/atoms";
import { lastFocusedCellIdAtom } from "@/core/cells/focus";

interface PanelOwnershipResult {
  isPanelOpen: boolean;
  togglePanel: () => void;
}

export function usePanelOwnership(
  id: string,
  cellId?: CellId | null,
): PanelOwnershipResult {
  let isPanelCellAware = useAtomValue(isCellAwareAtom);
  const [lastFocusedCellId, setLastFocusedCellId] = useAtom(
    lastFocusedCellIdAtom,
  );
  const [panelOwner, setPanelOwner] = useAtom(contextAwarePanelOwner);
  const [isContextAwarePanelOpen, setContextAwarePanelOpen] = useAtom(
    contextAwarePanelOpen,
  );
  const panelId = getPanelId(id, cellId);

  if (!cellId && isPanelCellAware) {
    Logger.error("CellId is not found, defaulting to fixed mode");
    isPanelCellAware = false;
  }

  const isPanelOpen = panelOwner === panelId && isContextAwarePanelOpen;

  // In cell-aware mode, update panel owner when cell is focused
  // Only set panel owner if no other table in this cell is currently the owner
  const thisCellIsFocused = lastFocusedCellId === cellId;
  const currentOwnerIsInThisCell =
    panelOwner && isPanelOwner(panelOwner, cellId);

  if (
    isPanelCellAware &&
    thisCellIsFocused &&
    panelOwner !== panelId &&
    !currentOwnerIsInThisCell
  ) {
    setPanelOwner(panelId);
  }

  function togglePanel() {
    if (isPanelOpen) {
      setPanelOwner(null);
      setContextAwarePanelOpen(false);
    } else {
      setPanelOwner(panelId);
      // if cell-aware, we want to focus on this cell when toggled open
      if (isPanelCellAware && cellId) {
        setLastFocusedCellId(cellId);
      }
      setContextAwarePanelOpen(true);
    }
  }

  return {
    isPanelOpen: isPanelOpen,
    togglePanel: togglePanel,
  };
}

/**
 * Get the unique ID for the panel based on the cell ID.
 * If the cell ID is not provided, the panel ID is just the table ID.
 */
function getPanelId(id: string, cellId?: CellId | null) {
  if (cellId) {
    return `${cellId}-${id}`;
  }
  return id;
}

/**
 * Check if the panel is owned by the cell.
 * If the cell ID is not provided, the panel is owned by the table.
 */
function isPanelOwner(panelId: string, cellId?: CellId | null) {
  if (cellId) {
    return panelId.startsWith(cellId);
  }
  return false;
}
