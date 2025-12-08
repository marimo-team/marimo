/* Copyright 2024 Marimo. All rights reserved. */

import { useNodes, useOnSelectionChange, useReactFlow } from "@xyflow/react";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { useHotkey } from "@/hooks/useHotkey";
import type { CanvasNode } from "../models";

/**
 * Hook that registers keyboard shortcuts for the canvas layout editor.
 *
 * Provides hotkeys for common graph editor operations:
 * - Cmd/Ctrl+A: Select all nodes
 * - Escape: Clear selection
 * - Delete/Backspace: Delete selected nodes (handled by ReactFlow's deleteKeyCode prop)
 *
 * Future enhancements could include:
 * - Cmd/Ctrl+D: Duplicate selected nodes
 * - Cmd/Ctrl+G: Group selected nodes
 * - Alignment shortcuts (align left, right, top, bottom, center)
 * - Distribution shortcuts (distribute horizontally, vertically)
 * - Zoom shortcuts (fit view, fit selection)
 *
 * @param isEditable - Whether the canvas is in edit mode (hotkeys are only active in edit mode)
 */
export function useCanvasHotkeys(isEditable: boolean) {
  const { setNodes, fitView } = useReactFlow();
  const nodes = useNodes<CanvasNode>();
  const [hasSelection, setHasSelection] = useState(false);

  // Track selection state efficiently
  useOnSelectionChange({
    onChange: ({ nodes }) => {
      setHasSelection(nodes.length > 0);
    },
  });

  const selectedNodeIds = useMemo(
    () => nodes.filter((node) => node.selected).map((node) => node.data.cellId),
    [nodes],
  );

  // Select all nodes (Cmd/Ctrl+A)
  const handleSelectAll = useEvent((evt?: KeyboardEvent) => {
    if (!isEditable) {
      return false;
    }

    // Prevent default browser select all
    evt?.preventDefault();

    // Select all nodes
    setNodes((nodes) =>
      nodes.map((node) => ({
        ...node,
        selected: true,
      })),
    );
  });

  // Clear selection (Escape)
  const handleClearSelection = useEvent((evt?: KeyboardEvent) => {
    if (!isEditable) {
      return false;
    }

    // Only clear if we have selected nodes
    if (!hasSelection) {
      return false;
    }

    evt?.preventDefault();

    // Clear all selections
    setNodes((nodes) =>
      nodes.map((node) => ({
        ...node,
        selected: false,
      })),
    );
  });

  // Fit view to all content (Cmd/Ctrl+0)
  const handleFitView = useEvent((evt?: KeyboardEvent) => {
    if (!isEditable) {
      return false;
    }

    evt?.preventDefault();

    // Fit view with animation
    fitView({
      padding: 0.2,
      duration: 300,
    });
  });

  // Register hotkeys
  useHotkey("global.selectAll", handleSelectAll);
  useHotkey("global.escape", handleClearSelection);

  return {
    selectedNodeIds,
    handleSelectAll,
    handleClearSelection,
    handleFitView,
  };
}
