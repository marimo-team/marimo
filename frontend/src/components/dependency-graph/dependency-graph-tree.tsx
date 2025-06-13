/* Copyright 2024 Marimo. All rights reserved. */

import type { Atom } from "jotai";
import { MapPinIcon } from "lucide-react";
import React, { type PropsWithChildren, useEffect, useState } from "react";
import useEvent from "react-use-event-hook";
import ReactFlow, {
  Background,
  BackgroundVariant,
  ControlButton,
  Controls,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "reactflow";
import {
  EdgeMarkerContext,
  nodeTypes,
} from "@/components/dependency-graph/custom-node";
import { lastFocusedCellIdAtom } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import type { Variables } from "@/core/variables/types";
import { Events } from "@/utils/events";
import { scrollAndHighlightCell } from "../editor/links/cell-link";
import { Tooltip } from "../ui/tooltip";
import { type NodeData, TreeElementsBuilder } from "./elements";
import { GraphSelectionPanel } from "./panels";
import type { GraphSelection, GraphSettings, LayoutDirection } from "./types";
import { layoutElements } from "./utils/layout";
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
  // eslint-disable-next-line react/hook-use-state
  const [initial] = useState(() => {
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
  });

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const api = useReactFlow();

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

  const handleClearSelection = () => {
    setSelection(undefined);
  };

  return (
    <EdgeMarkerContext value={layoutDirection}>
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
        <Controls position="bottom-right" showInteractive={false}>
          <Tooltip
            content="Jump to focused cell"
            delayDuration={200}
            side="left"
            asChild={false}
          >
            <ControlButton
              onMouseDown={Events.preventFocus}
              onClick={() => {
                const lastFocusedCell = store.get(lastFocusedCellIdAtom);
                // Zoom the graph to the last focused cell
                if (lastFocusedCell) {
                  const node = nodes.find(
                    (node) => node.id === lastFocusedCell,
                  );
                  if (node) {
                    api.fitView({
                      padding: 1,
                      duration: 600,
                      nodes: [node],
                    });
                    setSelection({ type: "node", id: lastFocusedCell });
                  }
                }
              }}
            >
              <MapPinIcon className="size-4" />
            </ControlButton>
          </Tooltip>
        </Controls>
        <GraphSelectionPanel
          selection={selection}
          variables={variables}
          edges={edges}
          onClearSelection={handleClearSelection}
        />
        {children}
      </ReactFlow>
    </EdgeMarkerContext>
  );
};
