/* Copyright 2024 Marimo. All rights reserved. */
import type {
  Edge,
  EdgeAddChange,
  EdgeRemoveChange,
  Node,
  NodeAddChange,
  NodeRemoveChange,
} from "reactflow";

export function getNodeChanges(
  prevNodes: Node[],
  nextNodes: Node[],
): Array<NodeAddChange | NodeRemoveChange> {
  const changes: Array<NodeAddChange | NodeRemoveChange> = [];
  const prevNodeIds = new Set(prevNodes.map((node) => node.id));
  const nextNodeIds = new Set(nextNodes.map((node) => node.id));

  for (const node of prevNodes) {
    if (!nextNodeIds.has(node.id)) {
      changes.push({ type: "remove", id: node.id });
    }
  }

  for (const node of nextNodes) {
    if (!prevNodeIds.has(node.id)) {
      changes.push({ type: "add", item: node });
    }
  }

  return changes;
}
export function getEdgeChanges(
  prevEdges: Edge[],
  nextEdges: Edge[],
): Array<EdgeAddChange | EdgeRemoveChange> {
  const changes: Array<EdgeAddChange | EdgeRemoveChange> = [];
  const prevEdgeIds = new Set(prevEdges.map((edge) => edge.id));
  const nextEdgeIds = new Set(nextEdges.map((edge) => edge.id));

  for (const edge of prevEdges) {
    if (!nextEdgeIds.has(edge.id)) {
      changes.push({ type: "remove", id: edge.id });
    }
  }

  for (const edge of nextEdges) {
    if (!prevEdgeIds.has(edge.id)) {
      changes.push({ type: "add", item: edge });
    }
  }

  return changes;
}
