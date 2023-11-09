/* Copyright 2023 Marimo. All rights reserved. */
import ReactFlow, {
  Node,
  Edge,
  MarkerType,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  PanOnScrollMode,
  useStore,
  useReactFlow,
  CoordinateExtent,
} from "reactflow";

import React, { useEffect, useMemo, useState } from "react";
import {
  CustomNode,
  getHeight,
} from "@/components/dependency-graph/custom-node";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/model/ids";
import { CellData } from "@/core/model/cells";
import { Atom } from "jotai";
import { store } from "@/core/state/jotai";

import "reactflow/dist/style.css";
import "./dependency-graph.css";
import { useDebouncedCallback } from "@/hooks/useDebounce";

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
  const [nodes, setNodes] = useNodesState(initialNodes);

  const [allEdges, setAllEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();

  // If the cellIds change, update the nodes.
  useEffect(() => {
    const { nodes, edges } = createElements(cellIds, cellAtoms, variables);
    setNodes(nodes);
    setAllEdges(edges);
  }, [cellIds, setNodes, variables, cellAtoms, setAllEdges]);

  // If the selected node changes, update the edges.
  useEffect(() => {
    if (selectedNodeId) {
      const selectedEdges = allEdges.filter((edge) => {
        const { source, target, data } = edge;

        return (
          (source === selectedNodeId && data.direction === "outputs") ||
          (target === selectedNodeId && data.direction === "inputs")
        );
      });
      setEdges(selectedEdges);
    } else {
      setEdges([]);
    }
  }, [selectedNodeId, setEdges, allEdges]);

  const instance = useReactFlow();
  const [width, height] = useStore(({ width, height }) => [width, height]);

  const debounceFitView = useDebouncedCallback(() => {
    instance.fitView({ duration: 100 });
  }, 100);

  // When the window is resized, fit the view to the graph.
  useEffect(() => {
    debounceFitView();
  }, [width, height, debounceFitView]);

  const translateExtent = useTranslateExtent(nodes, height);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      translateExtent={translateExtent}
      onNodeClick={(_event, node) => {
        const id = node.id;
        setSelectedNodeId(id);
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
    width: 250,
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

// Limit the extent of the graph to just the visible nodes.
// The top node and bottom node can be scrolled to the middle of the graph.
function useTranslateExtent(nodes: Node[], height: number): CoordinateExtent {
  const PADDING_Y = 10;

  return useMemo<CoordinateExtent>(() => {
    const top = nodes.reduce(
      (top, { position }) => Math.min(top, position.y - height / 2 - PADDING_Y),
      Number.POSITIVE_INFINITY
    );

    const bottom = nodes.reduce(
      (bottom, { position }) =>
        Math.max(bottom, position.y + height / 2 + PADDING_Y),
      Number.NEGATIVE_INFINITY
    );

    return [
      [Number.NEGATIVE_INFINITY, top],
      [Number.POSITIVE_INFINITY, bottom],
    ];
  }, [nodes, height]);
}
