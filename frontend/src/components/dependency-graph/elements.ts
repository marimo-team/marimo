/* Copyright 2024 Marimo. All rights reserved. */

import { CellData } from "@/core/cells/types";
import { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { Variables } from "@/core/variables/types";
import { Edge, MarkerType, Node, NodeProps } from "reactflow";
import { Atom } from "jotai";

export interface NodeData {
  atom: Atom<CellData>;
  forceWidth?: number;
}
export type CustomNodeProps = NodeProps<NodeData>;

export function getNodeHeight(linesOfCode: number) {
  const LINE_HEIGHT = 11; // matches TinyCode.css
  return Math.min(linesOfCode * LINE_HEIGHT + 35, 200);
}

interface ElementsBuilder {
  createElements: (
    cellIds: CellId[],
    cellAtoms: Array<Atom<CellData>>,
    variables: Variables,
  ) => { nodes: Array<Node<NodeData>>; edges: Edge[] };
}

export class VerticalElementsBuilder implements ElementsBuilder {
  private createEdge(source: CellId, target: CellId, direction: string): Edge {
    return {
      type: "smoothstep",
      pathOptions: {
        offset: 20,
        borderRadius: 100,
      },
      data: {
        direction: direction,
      },
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

  private createNode(
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

  createElements(
    cellIds: CellId[],
    cellAtoms: Array<Atom<CellData>>,
    variables: Variables,
  ) {
    let prevY = 0;
    const nodes: Array<Node<NodeData>> = [];
    const edges: Edge[] = [];
    let index = 0;
    for (const cellId of cellIds) {
      const node = this.createNode(cellId, cellAtoms[index], prevY);
      nodes.push(node);
      prevY = node.position.y + (node.height || 0);
      index++;
    }

    const visited = new Set<string>();
    for (const variable of Object.values(variables)) {
      const { declaredBy, usedBy } = variable;
      for (const fromId of declaredBy) {
        for (const toId of usedBy) {
          const key = `${fromId}-${toId}`;
          if (visited.has(key)) {
            continue;
          }
          visited.add(key);
          edges.push(
            this.createEdge(fromId, toId, "inputs"),
            this.createEdge(fromId, toId, "outputs"),
          );
        }
      }
    }
    return { nodes, edges };
  }
}

export class TreeElementsBuilder implements ElementsBuilder {
  private createEdge(source: CellId, target: CellId): Edge {
    return {
      animated: true,
      markerEnd: {
        type: MarkerType.Arrow,
      },
      id: `${source}-${target}`,
      source: source,
      sourceHandle: "outputs",
      targetHandle: "inputs",
      target: target,
    };
  }

  private createNode(id: string, atom: Atom<CellData>): Node<NodeData> {
    const linesOfCode = store.get(atom).code.trim().split("\n").length;
    const height = getNodeHeight(linesOfCode);
    return {
      id: id,
      data: { atom, forceWidth: 300 },
      width: 300,
      type: "custom",
      height: height,
      position: { x: 0, y: 0 },
    };
  }

  createElements(
    cellIds: CellId[],
    cellAtoms: Array<Atom<CellData>>,
    variables: Variables,
  ) {
    const nodes: Array<Node<NodeData>> = [];
    const edges: Edge[] = [];
    let index = 0;
    for (const cellId of cellIds) {
      const node = this.createNode(cellId, cellAtoms[index]);
      nodes.push(node);
      index++;
    }

    const visited = new Set<string>();
    for (const variable of Object.values(variables)) {
      const { declaredBy, usedBy } = variable;
      for (const fromId of declaredBy) {
        for (const toId of usedBy) {
          const key = `${fromId}-${toId}`;
          if (visited.has(key)) {
            continue;
          }
          visited.add(key);
          edges.push(this.createEdge(fromId, toId));
        }
      }
    }
    return { nodes, edges };
  }
}
