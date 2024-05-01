/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import { Edge, Panel } from "reactflow";
import { Button } from "../ui/button";
import {
  Rows3Icon,
  NetworkIcon,
  ArrowRightFromLineIcon,
  ArrowRightIcon,
  ArrowRightToLineIcon,
  WorkflowIcon,
  SquareFunction,
} from "lucide-react";
import { GraphLayoutView, GraphSelection } from "./types";
import { CellId } from "@/core/cells/ids";
import { CellLink } from "../editor/links/cell-link";
import { CellLinkList } from "../editor/links/cell-link-list";
import { VariableName } from "../variables/common";
import { Variables } from "@/core/variables/types";

interface Props {
  view: GraphLayoutView;
  onChange: (view: GraphLayoutView) => void;
}

export const GraphToolbar: React.FC<Props> = memo(({ onChange, view }) => {
  return (
    <Panel position="top-right" className="space-x-2">
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "_minimap_"}
        size="xs"
        onClick={() => onChange("_minimap_")}
      >
        <Rows3Icon className="w-4 h-4 mr-1" />
        Mini Map
      </Button>
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "TB"}
        size="xs"
        onClick={() => onChange("TB")}
      >
        <NetworkIcon className="w-4 h-4 mr-1" />
        Vertical Tree
      </Button>
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "LR"}
        size="xs"
        onClick={() => onChange("LR")}
      >
        <NetworkIcon className="w-4 h-4 mr-1 transform -rotate-90" /> Horizontal
        Tree
      </Button>
    </Panel>
  );
});
GraphToolbar.displayName = "GraphToolbar";

export const GraphSelectionPanel: React.FC<{
  selection: GraphSelection;
  edges: Edge[];
  variables: Variables;
}> = memo(({ selection, edges, variables }) => {
  if (!selection) {
    return null;
  }

  const renderSelection = () => {
    if (selection.type === "node") {
      const inputs = edges.flatMap((edge) =>
        edge.target === selection.id ? [edge.source as CellId] : [],
      );
      const outputs = edges.flatMap((edge) =>
        edge.source === selection.id ? [edge.target as CellId] : [],
      );
      return (
        <>
          <div className="font-bold py-2 flex items-center gap-2 border-b px-3">
            <SquareFunction className="w-5 h-5" />
            <CellLink cellId={selection.id} />
          </div>
          <div className="text-sm flex flex-col p-3 flex-1 justify-center">
            <div className="flex items-center gap-2">
              <span title="Inputs">
                <ArrowRightToLineIcon className="w-4 h-4 mr-2" />
              </span>
              <CellLinkList maxCount={3} cellIds={inputs} />
            </div>
            <div className="flex items-center gap-2">
              <span title="Outputs">
                <ArrowRightFromLineIcon className="w-4 h-4 mr-2" />
              </span>
              <CellLinkList maxCount={3} cellIds={outputs} />
            </div>
          </div>
        </>
      );
    }

    if (selection.type === "edge") {
      const variableUsed = Object.values(variables).filter(
        (variable) =>
          variable.declaredBy.includes(selection.source) &&
          variable.usedBy.includes(selection.target),
      );
      return (
        <>
          <div className="font-bold py-2 flex items-center gap-2 border-b px-3">
            <WorkflowIcon className="w-4 h-4" />
            <CellLink cellId={selection.source} />
            <ArrowRightIcon className="w-4 h-4" />
            <CellLink cellId={selection.target} />
          </div>
          <div className="grid grid-cols-3 gap-3 max-w-[350px] items-center text-sm p-3 flex-1">
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
        </>
      );
    }
  };

  return (
    <Panel position="bottom-left">
      <div className="min-h-[100px] shadow-md rounded-md border border-primary/40 my-4 min-w-[200px] bg-[var(--slate-1)] text-muted-foreground/80 flex flex-col">
        {renderSelection()}
      </div>
    </Panel>
  );
});

GraphSelectionPanel.displayName = "GraphSelectionPanel";
