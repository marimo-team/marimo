/* Copyright 2024 Marimo. All rights reserved. */
import ReactFlow, {
  Node,
  Edge,
  useEdgesState,
  useNodesState,
  PanOnScrollMode,
  useStore,
  useReactFlow,
  CoordinateExtent,
} from "reactflow";

import React, {
  PropsWithChildren,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { nodeTypes } from "@/components/dependency-graph/custom-node";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/cells/ids";
import { CellData } from "@/core/cells/types";
import { Atom } from "jotai";

import { useDebouncedCallback } from "@/hooks/useDebounce";
import { NodeData, VerticalElementsBuilder } from "./elements";
import useEvent from "react-use-event-hook";
import { scrollToCell } from "../editor/links/cell-link";
import { GraphSelectionPanel } from "./panels";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Array<Atom<CellData>>;
}

const elementsBuilder = new VerticalElementsBuilder();

export const DependencyGraphMinimap: React.FC<PropsWithChildren<Props>> = ({
  cellIds,
  variables,
  cellAtoms,
  children,
}) => {
  // State
  const { nodes: initialNodes, edges: allEdges } =
    elementsBuilder.createElements(cellIds, cellAtoms, variables, false);
  const [edges, setEdges] = useEdgesState([]);
  const [nodes, setNodes] = useNodesState(initialNodes);
  const [selectedNodeId, setSelectedNodeId] = useState<CellId>();
  const hasRenderer = useRef(false);

  // Subscriptions
  const instance = useReactFlow();
  const width = useStore(({ width }) => width);
  const height = useStore(({ height }) => height);

  // If the cellIds change, update the nodes.
  const syncChanges = useEvent(
    (elements: { nodes: Array<Node<NodeData>>; edges: Edge[] }) => {
      setNodes(elements.nodes);
      setEdges([]);
    },
  );

  // If the cellIds change, update the nodes.
  // Only on the second render, because the first render is the initial render.
  useEffect(() => {
    if (!hasRenderer.current) {
      hasRenderer.current = true;
      return;
    }
    syncChanges(
      elementsBuilder.createElements(cellIds, cellAtoms, variables, false),
    );
  }, [cellIds, variables, cellAtoms, syncChanges]);

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
    }
  }, [selectedNodeId, setEdges, allEdges]);

  const debounceFitView = useDebouncedCallback(() => {
    instance.fitView({ duration: 100 });
  }, 100);

  // When the window is resized, fit the view to the graph.
  useEffect(() => {
    if (!width || !height) {
      return;
    }
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
        if (id === selectedNodeId) {
          return;
        }
        setSelectedNodeId(id as CellId);
        setEdges([]);
      }}
      onNodeDoubleClick={(_event, node) => {
        scrollToCell(node.id as CellId, "focus");
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
    >
      {selectedNodeId && (
        <GraphSelectionPanel
          selection={{ type: "node", id: selectedNodeId }}
          variables={variables}
          edges={edges}
        />
      )}
      {children}
    </ReactFlow>
  );
};

// Limit the extent of the graph to just the visible nodes.
// The top node and bottom node can be scrolled to the middle of the graph.
function useTranslateExtent(nodes: Node[], height: number): CoordinateExtent {
  const PADDING_Y = 10;

  return useMemo<CoordinateExtent>(() => {
    const top = nodes.reduce(
      (top, { position }) => Math.min(top, position.y - height / 2 - PADDING_Y),
      Number.POSITIVE_INFINITY,
    );

    const bottom = nodes.reduce(
      (bottom, { position }) =>
        Math.max(bottom, position.y + height / 2 + PADDING_Y),
      Number.NEGATIVE_INFINITY,
    );

    return [
      [Number.NEGATIVE_INFINITY, top],
      [Number.POSITIVE_INFINITY, bottom],
    ];
  }, [nodes, height]);
}
