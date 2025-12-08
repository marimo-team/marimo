/* Copyright 2024 Marimo. All rights reserved. */

import type { Node } from "@xyflow/react";
import { useEffect } from "react";
import type { CellData } from "@/core/cells/types";
import { type CanvasNode, NODE_DEFAULTS } from "../models";
import { resolveCollisions } from "../resolve-collisions";

interface UseNewCellPositioningProps {
  cells: CellData[];
  nodes: Node[];
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
}

/**
 * Hook to handle positioning of newly added cells in the canvas
 * Extracts complex positioning logic from the main Canvas component
 */
export function useNewCellPositioning({
  cells,
  nodes,
  setNodes,
}: UseNewCellPositioningProps) {
  useEffect(() => {
    const cellIds = cells.map((c) => c.id);
    const nodeIds = nodes.map((n) => n.id);

    // Find cells that don't have corresponding nodes yet
    const newCellIds = cellIds.filter((id) => !nodeIds.includes(id));

    if (newCellIds.length === 0) {
      return;
    }

    let newPosition: { x: number; y: number } | null = null;
    let hasMetadata = false;

    // Check if we have position metadata from the AI prompt
    const aiMetaStr = sessionStorage.getItem("aiCellPositionMeta");
    if (aiMetaStr) {
      const aiMeta = JSON.parse(aiMetaStr) as {
        position: { x: number; y: number };
      };
      newPosition = aiMeta.position;
      hasMetadata = true;
      // Don't remove it yet - AI generates multiple cells sequentially
      // It will be cleared when the AI prompt is closed/accepted
    }

    // Check if we have position metadata from the add button (fallback)
    if (!hasMetadata) {
      const metaStr = sessionStorage.getItem("newCellPositionMeta");
      if (metaStr) {
        const meta = JSON.parse(metaStr) as {
          direction: "above" | "below" | "left" | "right";
          referencePosition: { x: number; y: number };
          referenceSize: { width: number; height: number };
        };
        sessionStorage.removeItem("newCellPositionMeta");
        hasMetadata = true;

        // Calculate position based on direction
        const padding = 40;

        switch (meta.direction) {
          case "above":
            newPosition = {
              x: meta.referencePosition.x,
              y: meta.referencePosition.y - NODE_DEFAULTS.height - padding,
            };
            break;
          case "below":
            newPosition = {
              x: meta.referencePosition.x,
              y: meta.referencePosition.y + meta.referenceSize.height + padding,
            };
            break;
          case "left":
            newPosition = {
              x: meta.referencePosition.x - NODE_DEFAULTS.width - padding,
              y: meta.referencePosition.y,
            };
            break;
          case "right":
            newPosition = {
              x: meta.referencePosition.x + meta.referenceSize.width + padding,
              y: meta.referencePosition.y,
            };
            break;
        }
      }
    }

    // Add the new node with calculated position
    if (hasMetadata && newPosition) {
      for (const newCellId of newCellIds) {
        const newNode: CanvasNode = {
          id: newCellId,
          type: "cell",
          position: newPosition,
          data: {
            cellId: newCellId,
            meta: {},
          },
          style: {
            width: NODE_DEFAULTS.width,
            height: NODE_DEFAULTS.height,
          },
        };
        setNodes((currentNodes) => [...currentNodes, newNode]);
      }

      // Run collision resolution after adding new cells
      setTimeout(() => {
        setNodes((nds) =>
          resolveCollisions(nds, {
            maxIterations: 100,
            overlapThreshold: 0,
            margin: 20,
          }),
        );
      }, 0);
    }
  }, [cells, nodes, setNodes]);
}
