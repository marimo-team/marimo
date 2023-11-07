/* Copyright 2023 Marimo. All rights reserved. */
import ReactFlow, {
  Node,
  Edge,
  MarkerType,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  PanOnScrollMode,
} from "reactflow";
import "reactflow/dist/style.css";

import React from "react";
import {
  CustomNode,
  getHeight,
} from "@/components/dependency-graph/custom-node";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/model/ids";
import { CellData } from "@/core/model/cells";
import { Atom } from "jotai";
import { store } from "@/core/state/jotai";
import { DependencyGraphConstants } from "./constants";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Array<Atom<CellData>>;
}

const nodeTypes = {
  custom: CustomNode,
};

export const DependencyGraph: React.FC<Props> = (props) => {
  return (
    <ReactFlowProvider>
      <DependencyGraphInternal {...props} />
    </ReactFlowProvider>
  );
};

const DependencyGraphInternal: React.FC<Props> = ({
  cellIds,
  variables,
  cellAtoms,
}) => {
  const { nodes: initialNodes, edges: initialEdges } = createElements(
    cellIds,
    cellAtoms,
    variables
  );
  const [edges, setEdges] = useEdgesState([]);
  const [nodes] = useNodesState(initialNodes);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_event, node) => {
        const id = node.id;
        const selectedEdges = initialEdges.filter(
          (edge) =>
            (edge.source === id && edge.data.direction === "outputs") ||
            (edge.target === id && edge.data.direction === "inputs")
        );
        console.log(selectedEdges.length);
        setEdges([]);
        requestAnimationFrame(() => {
          setEdges(selectedEdges);
        });
      }}
      // On
      snapToGrid={true}
      fitView={true}
      elementsSelectable={true}
      // Off
      minZoom={1}
      maxZoom={1}
      draggable={false}
      panOnScrollMode={PanOnScrollMode.Vertical}
      zoomOnDoubleClick={false}
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      selectNodesOnDrag={false}
      panOnDrag={false}
      preventScrolling={false}
      zoomOnPinch={false}
      panOnScroll={true}
      autoPanOnNodeDrag={false}
      autoPanOnConnect={false}
    />
  );
};

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

function createNode(id: string, atom: Atom<CellData>, prevY: number): Node {
  const linesOfCode = store.get(atom).code.trim().split("\n").length;
  const height = getHeight(linesOfCode);
  return {
    id: id,
    data: { atom },
    width: DependencyGraphConstants.nodeWidth,
    type: "custom",
    height: height,
    position: { x: 0, y: prevY + 20 },
  };
}

function createElements(
  cellIds: CellId[],
  cellAtoms: Array<Atom<CellData>>,
  variables: Variables
) {
  let prevY = 0;
  const nodes: Node[] = [];
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
          createEdge(fromId, toId, "outputs")
        );
      }
    }
  }
  return { nodes, edges };
}
