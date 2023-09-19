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

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const { isOpen, selectedPanel, panelLocation } = useChromeState();
  const { setIsOpen } = useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);

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
      maxSize={30}
      onCollapse={(collapsed) => setIsOpen(!collapsed)}
    >
      {selectedPanel === "errors" && <ErrorsPanel />}
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
