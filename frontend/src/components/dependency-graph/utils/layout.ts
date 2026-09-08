/* Copyright 2026 Marimo. All rights reserved. */
import { graphlib, layout } from "@dagrejs/dagre";
import type { Edge, Node } from "reactflow";
import type { NodeData } from "../elements";
import type { LayoutDirection } from "../types";

// Disconnected cells are stacked in a compact column to the side of the main
// graph, like TensorBoard's extracted/auxiliary nodes (extractXOffset 15,
// extractYOffset 20).
const ISLAND_GAP = 20;
const ISLAND_MARGIN = 40;
const ISLAND_MIN_COLUMN_HEIGHT = 320;

/**
 * Lay out cell nodes with dagre. Disconnected cells are pulled out of the
 * dagre flow and stacked in a compact column to the side of the main graph.
 */
export const layoutElements = ({
  nodes,
  edges,
  direction,
}: {
  nodes: Node<NodeData>[];
  edges: Edge[];
  direction: LayoutDirection;
}): { nodes: Node<NodeData>[]; edges: Edge[] } => {
  const g = new graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: direction,
    // Tight spacing mirroring TensorBoard's graph (nodesep 5, ranksep 25,
    // edgesep 5), nudged up a little since our nodes are wider ref boxes than
    // TensorBoard's op ellipses. The dagre default ranker (network-simplex)
    // gives cleaner layered routing with fewer crossings than longest-path.
    nodesep: 20,
    ranksep: 30,
    edgesep: 10,
  });

  // Disconnected cells are pulled out of the dagre flow and stacked to the
  // side, so they don't stretch the main graph's layout.
  const connectedIds = new Set<string>();
  for (const edge of edges) {
    connectedIds.add(edge.source);
    connectedIds.add(edge.target);
  }
  const isIsland = (node: Node<NodeData>) => !connectedIds.has(node.id);
  const flowNodes = nodes.filter((node) => !isIsland(node));
  const islands = nodes.filter(isIsland);

  edges.forEach((edge) => g.setEdge(edge.source, edge.target));
  flowNodes.forEach((node) => {
    g.setNode(node.id, {
      ...node,
      width: node.width ?? 0,
      height: node.height ?? 0,
    });
  });

  layout(g);

  // dagre reports node coords as centers; ReactFlow wants top-left.
  const topLeft = (id: string) => {
    const { x, y, width, height } = g.node(id);
    return { x: x - width / 2, y: y - height / 2 };
  };

  const cellNodes = flowNodes.map((node) => ({
    ...node,
    position: topLeft(node.id),
  }));

  const islandNodes = placeIslands(islands, cellNodes);
  return { nodes: [...cellNodes, ...islandNodes], edges };
};

/** Bounding box of already-positioned nodes (top-left position + size). */
export function boundingBox(nodes: Node[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  if (nodes.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const node of nodes) {
    const styleW = node.style?.width;
    const styleH = node.style?.height;
    const w = node.width ?? (typeof styleW === "number" ? styleW : 0);
    const h = node.height ?? (typeof styleH === "number" ? styleH : 0);
    minX = Math.min(minX, node.position.x);
    minY = Math.min(minY, node.position.y);
    maxX = Math.max(maxX, node.position.x + w);
    maxY = Math.max(maxY, node.position.y + h);
  }
  return { minX, minY, maxX, maxY };
}

/**
 * Stack disconnected nodes in a compact column (wrapping into more columns when
 * tall) just to the right of the main graph.
 */
export function placeIslands(
  islands: Node<NodeData>[],
  placed: Node[],
): Node<NodeData>[] {
  if (islands.length === 0) {
    return [];
  }
  const box = boundingBox(placed);
  const startX = (placed.length === 0 ? 0 : box.maxX) + ISLAND_MARGIN;
  const startY = placed.length === 0 ? 0 : box.minY;
  const columnHeight = Math.max(box.maxY - box.minY, ISLAND_MIN_COLUMN_HEIGHT);

  let x = startX;
  let y = startY;
  let columnWidth = 0;
  return islands.map((node) => {
    const h = node.height ?? 0;
    if (y > startY && y + h > startY + columnHeight) {
      // Wrap to the next column.
      x += columnWidth + ISLAND_MARGIN;
      y = startY;
      columnWidth = 0;
    }
    const position = { x, y };
    y += h + ISLAND_GAP;
    columnWidth = Math.max(columnWidth, node.width ?? 0);
    return { ...node, position };
  });
}
