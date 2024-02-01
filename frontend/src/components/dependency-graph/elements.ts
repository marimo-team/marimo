/* Copyright 2024 Marimo. All rights reserved. */

import { CellData } from "@/core/cells/types";
import { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { Variables } from "@/core/variables/types";
import { Edge, MarkerType, Node, NodeProps } from "reactflow";
import { Atom } from "jotai";

export interface NodeData {
  atom: Atom<CellData>;
}
export type CustomNodeProps = NodeProps<NodeData>;

export function getNodeHeight(linesOfCode: number) {
  const LINE_HEIGHT = 11; // matches TinyCode.css
  return Math.min(linesOfCode * LINE_HEIGHT + 35, 200);
}

/* Copyright 2024 Marimo. All rights reserved. */
function createEdge(source: CellId, target: CellId, direction: string): Edge {
  return {
    type: "smoothstep",
    pathOptions: {
      offset: 20,
      borderRadius: 100,
    },
    data: {
      direction: direction,
    },
    // animated: true,
    markerEnd: {
      type: MarkerType.Arrow,
    },
    id: `${source}-${target}-${direction}`,
    source: source,
    sourceHandle: direction,
    targetHandle: direction,
    target: target,
  };
}

function createNode(
  id: string,
  atom: Atom<CellData>,
  prevY: number,
): Node<NodeData> {
  const linesOfCode = store.get(atom).code.trim().split("\n").length;
  const height = getNodeHeight(linesOfCode);
  return {
    id: id,
    data: { atom },
    width: 250,
    type: "custom",
    height: height,
    position: { x: 0, y: prevY + 20 },
  };
}

export function createElements(
  cellIds: CellId[],
  cellAtoms: Array<Atom<CellData>>,
  variables: Variables,
) {
  let prevY = 0;
  const nodes: Array<Node<NodeData>> = [];
  const edges: Edge[] = [];
  let index = 0;
  for (const cellId of cellIds) {
    const node = createNode(cellId, cellAtoms[index], prevY);
    nodes.push(node);
    prevY = node.position.y + (node.height || 0);
    index++;
  }

  for (const variable of Object.values(variables)) {
    const { declaredBy, usedBy } = variable;
    for (const fromId of declaredBy) {
      for (const toId of usedBy) {
        edges.push(
          createEdge(fromId, toId, "inputs"),
          createEdge(fromId, toId, "outputs"),
        );
      }
    }
  }
  return { nodes, edges };
}
