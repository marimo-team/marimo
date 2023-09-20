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
import { useChromeActions, useChromeState } from "../state";
import { cn } from "@/lib/utils";
import { createStorage } from "./storage";
import { VariableTable } from "@/components/variables/variables-table";
import { useVariables } from "@/core/variables/state";
import { useCellIds } from "@/core/state/cells";
import { Button } from "@/components/ui/button";
import { XIcon } from "lucide-react";

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const { isOpen, selectedPanel, panelLocation } = useChromeState();
  const { setIsOpen } = useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);
  const variables = useVariables();
  const cellIds = useCellIds();

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
    <Panel id="app" key={`app-${panelLocation}`} className="relative h-full">
      {children}
    </Panel>
  );

  const resizeHandle = (
    <PanelResizeHandle
      className={cn(
        "border-border no-print",
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
      className="bg-[var(--sage-1)] no-print"
      minSize={10}
      // We can't make the default size greater than 0, otherwise it will start open
      defaultSize={0}
      maxSize={45}
      onResize={(size, prevSize) => {
        // This means it started closed and is opening for the first time
        if (prevSize === 0 && size === 10) {
          sidebarRef.current?.resize(30);
        }
      }}
      onCollapse={(collapsed) => setIsOpen(!collapsed)}
    >
      <div className="flex flex-col h-full flex-1">
        <div className="p-3 border-b flex justify-between items-center">
          <div className="text-sm font-medium text-[var(--sage-11)] uppercase tracking-wide font-semibold flex-1">
            Variables
          </div>
          <Button
            className="m-0"
            size="xs"
            variant="text"
            onClick={() => setIsOpen(false)}
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </div>
        {/* {selectedPanel === "errors" && <ErrorsPanel />} */}
        {selectedPanel === "variables" && (
          <VariableTable
            className="flex-1"
            cellIds={cellIds}
            variables={variables}
          />
        )}
      </div>
    </Panel>
  );

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <PanelGroup
        key={panelLocation}
        autoSaveId={`marimo:chrome`}
        direction={panelLocation === "left" ? "horizontal" : "vertical"}
        storage={createStorage(panelLocation)}
      >
        {panelLocation === "left" ? helperPane : appBody}
        {resizeHandle}
        {panelLocation === "left" ? appBody : helperPane}
      </PanelGroup>
      <Footer />
    </div>
  );
};
