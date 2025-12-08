/* Copyright 2024 Marimo. All rights reserved. */
import { graphlib, layout } from "@dagrejs/dagre";
import type { Edge, Node } from "reactflow";
import type { LayoutDirection, LayoutRanker } from "../types";

const g = new graphlib.Graph().setDefaultEdgeLabel(() => ({}));

export const layoutElements = ({
  nodes,
  edges,
  direction,
  ranker = "longest-path",
}: {
  nodes: Node[];
  edges: Edge[];
  direction: LayoutDirection;
  ranker?: LayoutRanker;
}) => {
  g.setGraph({
    rankdir: direction,
    nodesep: 150,
    ranksep: 200,
    ranker: ranker,
  });

  edges.forEach((edge) => g.setEdge(edge.source, edge.target));
  nodes.forEach((node) =>
    g.setNode(node.id, {
      ...node,
      width: node.width ?? 0,
      height: node.height ?? 0,
    }),
  );

  layout(g);

  return {
    nodes: nodes.map((node) => {
      const { x, y } = g.node(node.id);

      return { ...node, position: { x, y } };
    }),
    edges,
  };
};
