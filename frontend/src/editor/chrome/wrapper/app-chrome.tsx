/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren, useEffect } from "react";
import {
  PanelGroup,
  Panel,
  PanelResizeHandle,
  ImperativePanelHandle,
} from "react-resizable-panels";
import { Footer } from "./footer";
import "./app-chrome.css";
import { ErrorsPanel } from "../panels/error-panel";
import { useChromeActions, useChromeState } from "../state";
import { cn } from "@/lib/utils";
import { createStorage } from "./storage";
import { VariableTable } from "@/components/variables/variables-table";
import { useVariables } from "@/core/variables/state";

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const { isOpen, selectedPanel, panelLocation } = useChromeState();
  const { setIsOpen } = useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);
  const variables = useVariables();

  // sync sidebar
  useEffect(() => {
    if (!sidebarRef.current) {
      return;
    }

    const isCurrentlyCollapsed = sidebarRef.current.getCollapsed();
    if (isOpen && isCurrentlyCollapsed) {
      sidebarRef.current.expand();
    }
    if (!isOpen && !isCurrentlyCollapsed) {
      sidebarRef.current.collapse();
    }
  }, [isOpen]);

  const appBody = (
    <Panel
      id="app"
      key={`app-${panelLocation}`}
      style={{ height: "100%", overflow: "auto" }}
    >
      {children}
    </Panel>
  );

  const resizeHandle = (
    <PanelResizeHandle
      className={cn(
        "border-border",
        isOpen ? "resize-handle" : "resize-handle-collapsed",
        panelLocation === "left" ? "vertical" : "horizontal"
      )}
    />
  );

  const helperPane = (
    <Panel
      ref={sidebarRef}
      id="helper"
      key={`helper-${panelLocation}`}
      collapsedSize={0}
      collapsible={true}
      className="bg-[var(--sage-1)]"
      minSize={10}
      defaultSize={20}
      maxSize={45}
      onCollapse={(collapsed) => setIsOpen(!collapsed)}
    >
      <div className="flex flex-col h-full flex-1">
        <div className="text-sm font-medium text-[var(--sage-11)] uppercase tracking-wide font-semibold p-3 border-b">
          Variables
        </div>
        {selectedPanel === "errors" && <ErrorsPanel />}
        <VariableTable
          className="flex-1"
          cellIds={[]}
          variables={{
            a: {
              name: "a",
              declaredBy: ["1"],
              usedBy: ["2"],
              dataType: "number",
              value: '1',
            },
            b: {
              name: "b",
              declaredBy: ["2"],
              usedBy: ["3"],
              dataType: "dataframe",
              value: '<dataframe 12367 8123871623 816238 7>',
            },
            my_super_super_long_variable_name: {
              name: "my_super_super_long_variable_name",
              declaredBy: ["3"],
              usedBy: Array.from({ length: 15 }, (_, i) => `${i + 4}`),
            },
            c: {
              name: "c",
              declaredBy: ["4"],
              dataType: "number",
              value: '1',
              usedBy: Array.from({ length: 3 }, (_, i) => `${i + 4}`),
            },
            d: {
              name: "has_error",
              declaredBy: ["4", "5"],
              usedBy: Array.from({ length: 3 }, (_, i) => `${i + 4}`),
            },
          } as any} />
      </div>
    </Panel>
  );

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <PanelGroup
        key={panelLocation}
        autoSaveId={`marimo:chrome`}
        direction={panelLocation === "left" ? "horizontal" : "vertical"}
      // storage={createStorage(panelLocation)}
      >
        {/* {panelLocation === "left" ? helperPane : appBody}
        {resizeHandle}
        {panelLocation === "left" ? appBody : helperPane} */}
        {helperPane}
        {resizeHandle}
        {appBody}
      </PanelGroup>
      <Footer />
    </div>
  );
};
