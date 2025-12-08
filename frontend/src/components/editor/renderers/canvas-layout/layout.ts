/* Copyright 2024 Marimo. All rights reserved. */

import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";
import type {
  LayoutDirection,
  LayoutRanker,
} from "@/components/dependency-graph/types";
import { getNodeDimensions } from "./utils";

/**
 * Calculate the bounding box of a set of nodes
 */
function getBoundingBox(nodes: Node[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} | null {
  if (nodes.length === 0) {
    return null;
  }

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const node of nodes) {
    const { width, height } = getNodeDimensions(node);
    const x1 = node.position.x;
    const y1 = node.position.y;
    const x2 = x1 + width;
    const y2 = y1 + height;

    minX = Math.min(minX, x1);
    minY = Math.min(minY, y1);
    maxX = Math.max(maxX, x2);
    maxY = Math.max(maxY, y2);
  }

  return { minX, minY, maxX, maxY };
}

/**
 * Layout elements using dagre graph layout algorithm
 */
export const layoutElements = ({
  nodes,
  edges,
  direction,
  ranker = "longest-path",
  boundaryNodes,
}: {
  nodes: Node[];
  edges: Edge[];
  direction: LayoutDirection;
  ranker?: LayoutRanker;
  /** Nodes that act as boundaries - the layout will be positioned outside their bounds */
  boundaryNodes?: Node[];
}) => {
  // Create a fresh graph instance for each layout call to avoid state accumulation
  const dagreGraph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === "LR";

  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 150,
    ranksep: 200,
    ranker: ranker,
  });

  nodes.forEach((node) => {
    const { width, height } = getNodeDimensions(node);

    dagreGraph.setNode(node.id, {
      width,
      height,
    });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const { width: nodeWidth, height: nodeHeight } = getNodeDimensions(node);

    const newNode = {
      ...node,
      targetPosition: isHorizontal ? "left" : "top",
      sourcePosition: isHorizontal ? "right" : "bottom",
      // We are shifting the dagre node position (anchor=center center) to the top left
      // so it matches the React Flow node anchor point (top left).
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };

    return newNode;
  });

  // If boundary nodes are provided, offset the layout to be outside their bounds
  if (boundaryNodes && boundaryNodes.length > 0) {
    const boundaryBox = getBoundingBox(boundaryNodes);
    const layoutBox = getBoundingBox(newNodes);

    if (boundaryBox && layoutBox) {
      const padding = 100; // Padding between boundary and new layout

      // Calculate offset based on direction
      let offsetX = 0;
      let offsetY = 0;

      if (isHorizontal) {
        // For horizontal layout (LR), place to the right of boundary
        offsetX = boundaryBox.maxX + padding - layoutBox.minX;
      } else {
        // For vertical layout (TB), place below boundary
        offsetY = boundaryBox.maxY + padding - layoutBox.minY;
      }

      // Apply offset to all new nodes
      return {
        nodes: newNodes.map((node) => ({
          ...node,
          position: {
            x: node.position.x + offsetX,
            y: node.position.y + offsetY,
          },
        })),
        edges,
      };
    }
  }

  return { nodes: newNodes, edges };
};
