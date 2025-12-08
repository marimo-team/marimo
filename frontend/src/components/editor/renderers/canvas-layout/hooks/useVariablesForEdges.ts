/* Copyright 2024 Marimo. All rights reserved. */

import { MarkerType } from "@xyflow/react";
import { useMemo } from "react";
import type { CellId } from "@/core/cells/ids";
import { useVariables } from "@/core/variables/state";
import type { CanvasEdge } from "../models";

/**
 * Hook that creates edges based on variable dependencies.
 * Listens to variables state and generates edges from cells that declare
 * variables to cells that use those variables.
 */
export function useVariablesForEdges(): CanvasEdge[] {
  const variables = useVariables();

  return useMemo(() => {
    const edges: CanvasEdge[] = [];
    const visited = new Set<string>();

    // Iterate through all variables and create edges
    for (const variable of Object.values(variables)) {
      const { declaredBy, usedBy } = variable;

      // Create edges from each declaring cell to each using cell
      for (const fromId of declaredBy) {
        for (const toId of usedBy) {
          // Create a unique key to avoid duplicate edges
          const key = `${fromId}-${toId}`;
          if (visited.has(key)) {
            continue;
          }
          visited.add(key);

          // Create edge from source (declaredBy) to target (usedBy)
          edges.push(createEdge(fromId, toId));
        }
      }
    }

    return edges;
  }, [variables]);
}

/**
 * Creates a canvas edge between two cells
 */
function createEdge(source: CellId, target: CellId): CanvasEdge {
  return {
    id: `edge-${source}-${target}`,
    source,
    target,
    type: "smoothstep",
    animated: true,
    markerEnd: {
      type: MarkerType.ArrowClosed,
    },
    style: {
      strokeWidth: 2,
      stroke: "#3b82f6",
    },
  };
}
