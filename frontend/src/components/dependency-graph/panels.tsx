/* Copyright 2024 Marimo. All rights reserved. */

import {
  ArrowRightFromLineIcon,
  ArrowRightIcon,
  ArrowRightToLineIcon,
  MoreVerticalIcon,
  NetworkIcon,
  Rows3Icon,
  SettingsIcon,
  SquareFunction,
  WorkflowIcon,
  XIcon,
} from "lucide-react";
import React, { memo } from "react";
import { type Edge, Panel } from "reactflow";
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { goToVariableDefinition } from "@/core/codemirror/go-to-definition/commands";
import type { Variable, Variables } from "@/core/variables/types";
import { ConnectionCellActionsDropdown } from "../editor/cell/cell-actions";
import { CellLink } from "../editor/links/cell-link";
import { CellLinkList } from "../editor/links/cell-link-list";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Label } from "../ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { VariableName } from "../variables/common";
import type { GraphLayoutView, GraphSelection, GraphSettings } from "./types";

interface Props {
  view: GraphLayoutView;
  onChange: (view: GraphLayoutView) => void;
  settings: GraphSettings;
  onSettingsChange: (settings: GraphSettings) => void;
}

export const GraphToolbar: React.FC<Props> = memo(
  ({ onChange, view, settings, onSettingsChange }) => {
    const handleSettingChange = <K extends keyof GraphSettings>(
      key: K,
      value: GraphSettings[K],
    ) => {
      onSettingsChange({ ...settings, [key]: value });
    };

    const settingsButton = (
      <Popover>
        <PopoverTrigger asChild={true}>
          <Button variant="text" size="xs">
            <SettingsIcon className="w-4 h-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-2 text-muted-foreground">
          <div className="font-semibold pb-4">Settings</div>
          <div className="flex items-center gap-2">
            <Checkbox
              data-testid="hide-pure-markdown-checkbox"
              id="hide-pure-markdown"
              checked={settings.hidePureMarkdown}
              onCheckedChange={(checked) =>
                handleSettingChange("hidePureMarkdown", Boolean(checked))
              }
            />
            <Label htmlFor="hide-pure-markdown">Hide pure markdown</Label>
          </div>
        </PopoverContent>
      </Popover>
    );

    return (
      <Panel position="top-right" className="flex flex-col items-end gap-2">
        <div className="flex gap-2">
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
            <NetworkIcon className="w-4 h-4 mr-1 transform -rotate-90" />{" "}
            Horizontal Tree
          </Button>
        </div>
        {view !== "_minimap_" && settingsButton}
      </Panel>
    );
  },
);
GraphToolbar.displayName = "GraphToolbar";

export const GraphSelectionPanel: React.FC<{
  selection: GraphSelection;
  onClearSelection: () => void;
  edges: Edge[];
  variables: Variables;
}> = memo(({ selection, edges, variables, onClearSelection }) => {
  if (!selection) {
    return null;
  }

  // Highlight the variable in the cell editor
  const highlightInCell = (cellId: CellId, variableName: string) => {
    const editorView = getCellEditorView(cellId);
    if (editorView) {
      goToVariableDefinition(editorView, variableName);
    }
  };

  const renderSelection = () => {
    if (selection.type === "node") {
      const variablesUsed = Object.values(variables).filter((variable) =>
        variable.usedBy.includes(selection.id),
      );
      const variablesDeclared = Object.values(variables).filter((variable) =>
        variable.declaredBy.includes(selection.id),
      );

      const renderVariables = (
        variables: Variable[],
        direction: "in" | "out",
      ) => (
        <>
          {variables.length === 0 && (
            <div className="text-muted-foreground text-sm text-center">--</div>
          )}
          <div className="grid grid-cols-5 gap-3 items-center text-sm py-1 flex-1 empty:hidden">
            {variables.map((variable) => (
              <React.Fragment key={variable.name}>
                <VariableName
                  declaredBy={variable.declaredBy}
                  name={variable.name}
                />
                <div
                  className="truncate col-span-2"
                  title={variable.value ?? ""}
                >
                  {variable.value}
                  <span className="ml-1 truncate text-foreground/60 font-mono">
                    ({variable.dataType})
                  </span>
                </div>
                <div className="truncate col-span-2 gap-1 items-center">
                  <CellLinkList
                    skipScroll={true}
                    onClick={() =>
                      highlightInCell(
                        direction === "in"
                          ? variable.declaredBy[0]
                          : variable.usedBy[0],
                        variable.name,
                      )
                    }
                    maxCount={3}
                    cellIds={variable.usedBy}
                  />
                </div>
              </React.Fragment>
            ))}
          </div>
        </>
      );

      return (
        <>
          <div className="font-bold py-2 flex items-center gap-2 border-b px-3">
            <SquareFunction className="w-5 h-5" />
            <CellLink cellId={selection.id} />
            <div className="flex-1" />
            <ConnectionCellActionsDropdown cellId={selection.id}>
              <Button variant="ghost" size="icon">
                <MoreVerticalIcon className="w-4 h-4" />
              </Button>
            </ConnectionCellActionsDropdown>
            <Button
              variant="text"
              size="icon"
              onClick={() => {
                onClearSelection();
              }}
            >
              <XIcon className="w-4 h-4" />
            </Button>
          </div>
          <div className="text-sm flex flex-col py-3 pl-2 pr-4 flex-1 justify-center">
            <div className="flex flex-col gap-2">
              <span className="flex items-center gap-2 font-semibold">
                <ArrowRightFromLineIcon className="w-4 h-4" />
                Outputs
              </span>
              {renderVariables(variablesDeclared, "out")}
            </div>
            <hr className="border-divider my-3" />
            <div className="flex flex-col gap-2">
              <span className="flex items-center gap-2 font-semibold">
                <ArrowRightToLineIcon className="w-4 h-4" />
                Inputs
              </span>
              {renderVariables(variablesUsed, "in")}
            </div>
          </div>
        </>
      );
    }

    if (selection.type === "edge") {
      const edgeVariables = Object.values(variables).filter(
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
          <div className="grid grid-cols-4 gap-3 max-w-[350px] items-center text-sm p-3 flex-1">
            {edgeVariables.map((variable) => (
              <React.Fragment key={variable.name}>
                <VariableName
                  declaredBy={variable.declaredBy}
                  name={variable.name}
                  onClick={() => {
                    highlightInCell(variable.declaredBy[0], variable.name);
                  }}
                />
                <div className="truncate text-foreground/60 font-mono">
                  {variable.dataType}
                </div>
                <div
                  className="truncate col-span-2"
                  title={variable.value ?? ""}
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
    <Panel
      position="bottom-left"
      className="max-h-[90%] flex flex-col w-[calc(100%-5rem)]"
    >
      <div className="min-h-[100px] shadow-md rounded-md border max-w-[550px] border-primary/40 my-4 min-w-[240px] bg-[var(--slate-1)] text-muted-foreground/80 flex flex-col overflow-y-auto">
        {renderSelection()}
      </div>
    </Panel>
  );
});

GraphSelectionPanel.displayName = "GraphSelectionPanel";
