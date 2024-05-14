/* Copyright 2024 Marimo. All rights reserved. */
import ReactFlow, {
  useEdgesState,
  useNodesState,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
} from "reactflow";

import React, { PropsWithChildren, useEffect, useMemo, useState } from "react";
import {
  EdgeMarkerContext,
  nodeTypes,
} from "@/components/dependency-graph/custom-node";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/cells/ids";
import { CellData } from "@/core/cells/types";
import { Atom } from "jotai";

import { NodeData, TreeElementsBuilder } from "./elements";
import { layoutElements } from "./utils/layout";
import { GraphSelection, GraphSettings, LayoutDirection } from "./types";
import useEvent from "react-use-event-hook";
import { scrollAndHighlightCell } from "../editor/links/cell-link";
import { GraphSelectionPanel } from "./panels";
import { useFitToViewOnDimensionChange } from "./utils/useFitToViewOnDimensionChange";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Array<Atom<CellData>>;
  layoutDirection: LayoutDirection;
  settings: GraphSettings;
}

const elementsBuilder = new TreeElementsBuilder();

export const DependencyGraphTree: React.FC<PropsWithChildren<Props>> = ({
  cellIds,
  variables,
  cellAtoms,
  children,
  layoutDirection,
  settings,
}) => {
  const initial = useMemo(() => {
    let elements = elementsBuilder.createElements(
      cellIds,
      cellAtoms,
      variables,
      settings.hidePureMarkdown,
    );
    elements = layoutElements(elements.nodes, elements.edges, {
      direction: layoutDirection,
    });

    return elements;
    // Only run once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  const syncChanges = useEvent(
    (elements: { nodes: Array<Node<NodeData>>; edges: Edge[] }) => {
      // Layout the elements
      const result = layoutElements(elements.nodes, elements.edges, {
        direction: layoutDirection,
      });
      setNodes(result.nodes);
      setEdges(result.edges);
    },
  );

  // If the cellIds change, update the nodes.
  useEffect(() => {
    syncChanges(
      elementsBuilder.createElements(
        cellIds,
        cellAtoms,
        variables,
        settings.hidePureMarkdown,
      ),
    );
  }, [cellIds, variables, cellAtoms, syncChanges, settings.hidePureMarkdown]);

  const [selection, setSelection] = useState<GraphSelection>();
  useFitToViewOnDimensionChange();

  return (
    <EdgeMarkerContext.Provider value={layoutDirection}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        minZoom={0.2}
        fitViewOptions={{
          minZoom: 0.5,
          maxZoom: 1.5,
        }}
        onNodeClick={(_event, node) => {
          setSelection({ type: "node", id: node.id as CellId });
        }}
        onEdgeClick={(_event, edge) => {
          const { source, target } = edge;
          setSelection({
            type: "edge",
            source: source as CellId,
            target: target as CellId,
          });
        }}
        onNodeDoubleClick={(_event, node) => {
          scrollAndHighlightCell(node.id as CellId, "focus");
        }}
        fitView={true}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        zoomOnDoubleClick={false}
        nodesConnectable={false}
      >
        <Background color="#ccc" variant={BackgroundVariant.Dots} />
        <Controls position="bottom-right" showInteractive={false} />
        <GraphSelectionPanel
          selection={selection}
          variables={variables}
          edges={edges}
        />
        {children}
      </ReactFlow>
    </EdgeMarkerContext.Provider>
  );
};
