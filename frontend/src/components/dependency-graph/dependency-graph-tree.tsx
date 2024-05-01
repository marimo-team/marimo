/* Copyright 2024 Marimo. All rights reserved. */
import ReactFlow, {
  useEdgesState,
  useNodesState,
  Controls,
  Background,
  BackgroundVariant,
  Node,
  Edge,
  Panel,
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
import { getLayoutedElements } from "./utils/layout";
import { LayoutDirection } from "./types";
import useEvent from "react-use-event-hook";
import { getNodeChanges, getEdgeChanges } from "./utils/changes";
import { CellLink, scrollToCell } from "../editor/links/cell-link";
import {
  ArrowRightFromLineIcon,
  ArrowRightIcon,
  ArrowRightToLineIcon,
  WorkflowIcon,
} from "lucide-react";
import { CellLinkList } from "../editor/links/cell-link-list";
import { VariableName } from "../variables/common";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Array<Atom<CellData>>;
  layoutDirection: LayoutDirection;
}

type Selection =
  | {
      type: "node";
      id: CellId;
    }
  | {
      type: "edge";
      source: CellId;
      target: CellId;
    }
  | undefined;

const elementsBuilder = new TreeElementsBuilder();

export const DependencyGraphTree: React.FC<PropsWithChildren<Props>> = ({
  cellIds,
  variables,
  cellAtoms,
  children,
  layoutDirection,
}) => {
  const initial = useMemo(() => {
    let elements = elementsBuilder.createElements(
      cellIds,
      cellAtoms,
      variables,
    );
    elements = getLayoutedElements(elements.nodes, elements.edges, {
      direction: layoutDirection,
    });

    return elements;
    // Only run once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [nodes, _setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, _setEdges, onEdgesChange] = useEdgesState(initial.edges);

  const syncChanges = useEvent(
    (elements: { nodes: Array<Node<NodeData>>; edges: Edge[] }) => {
      const nodeChanges = getNodeChanges(nodes, elements.nodes);
      const edgeChanges = getEdgeChanges(edges, elements.edges);

      onNodesChange(nodeChanges);
      onEdgesChange(edgeChanges);
    },
  );

  // If the cellIds change, update the nodes.
  useEffect(() => {
    syncChanges(elementsBuilder.createElements(cellIds, cellAtoms, variables));
  }, [cellIds, variables, cellAtoms, syncChanges]);

  const [selection, setSelection] = useState<Selection>();

  const renderSelection = () => {
    if (!selection) {
      return null;
    }

    if (selection.type === "node") {
      const inputs = edges.flatMap((edge) =>
        edge.target === selection.id ? [edge.source as CellId] : [],
      );
      const outputs = edges.flatMap((edge) =>
        edge.source === selection.id ? [edge.target as CellId] : [],
      );
      return (
        <div>
          <div className="text-foreground/60 font-bold mb-4 flex items-center gap-1">
            <WorkflowIcon className="w-4 h-4" />
            <CellLink cellId={selection.id} />
          </div>
          <div className="text-sm text-muted-foreground flex flex-col">
            <div className="flex items-center gap-2">
              <ArrowRightToLineIcon className="w-5 h-5 mr-2" />
              <CellLinkList maxCount={3} cellIds={inputs} />
            </div>
            <div className="flex items-center gap-2">
              <ArrowRightFromLineIcon className="w-5 h-5 mr-2" />
              <CellLinkList maxCount={3} cellIds={outputs} />
            </div>
          </div>
        </div>
      );
    }

    if (selection.type === "edge") {
      const variableUsed = Object.values(variables).filter(
        (variable) =>
          variable.declaredBy.includes(selection.source) &&
          variable.usedBy.includes(selection.target),
      );
      return (
        <div>
          <div className="text-foreground/60 font-bold mb-4 flex items-center gap-1">
            <WorkflowIcon className="w-4 h-4" />
            <CellLink cellId={selection.source} />
            <ArrowRightIcon className="w-4 h-4" />
            <CellLink cellId={selection.target} />
          </div>
          <div className="grid grid-cols-3 gap-3 max-w-[250px] items-center text-sm">
            {variableUsed.map((variable) => (
              <React.Fragment key={variable.name}>
                <VariableName
                  declaredBy={variable.declaredBy}
                  name={variable.name}
                />
                <div className="text-ellipsis overflow-hidden whitespace-nowrap text-foreground/60 font-mono">
                  {variable.dataType}
                </div>
                <div
                  className="text-ellipsis overflow-hidden whitespace-nowrap"
                  title={variable.value}
                >
                  {variable.value}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      );
    }
  };

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
          scrollToCell(node.id as CellId, "focus");
        }}
        fitView={true}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        zoomOnDoubleClick={false}
        nodesConnectable={false}
      >
        <Background color="#ccc" variant={BackgroundVariant.Dots} />
        <Controls position="bottom-right" showInteractive={false} />
        <Panel position="bottom-left">
          {selection && (
            <div className="min-h-[100px] p-3 shadow-md rounded-md border border-primary/40 my-4 min-w-[200px] bg-[var(--slate-1)]">
              {renderSelection()}
            </div>
          )}
        </Panel>
        {children}
      </ReactFlow>
    </EdgeMarkerContext.Provider>
  );
};
