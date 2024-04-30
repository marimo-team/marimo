/* Copyright 2024 Marimo. All rights reserved. */
import { graphlib, layout } from "@dagrejs/dagre";
import { Edge, Node } from "reactflow";
import { LayoutDirection } from "../types";

const g = new graphlib.Graph().setDefaultEdgeLabel(() => ({}));

const PADDING = 30;

export const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  options: { direction: LayoutDirection },
) => {
  g.setGraph({ rankdir: options.direction });

  edges.forEach((edge) => g.setEdge(edge.source, edge.target));
  nodes.forEach((node) =>
    g.setNode(node.id, {
      ...node,
      width: (node.width || 0) + PADDING,
      height: (node.height || 0) + PADDING,
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
