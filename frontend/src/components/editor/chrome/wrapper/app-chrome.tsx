/* Copyright 2024 Marimo. All rights reserved. */
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
import { cn } from "@/utils/cn";
import { createStorage } from "./storage";
import { Button } from "@/components/ui/button";
import { XIcon } from "lucide-react";
import { ErrorsPanel } from "../panels/error-panel";
import { OutlinePanel } from "../panels/outline-panel";
import { DependencyGraphPanel } from "@/components/editor/chrome/panels/dependency-graph-panel";
import { VariablePanel } from "../panels/variable-panel";
import { LogsPanel } from "../panels/logs-panel";
import { DocumentationPanel } from "../panels/documentation-panel";
import { FileExplorerPanel } from "../panels/file-explorer-panel";
import { SnippetsPanel } from "../panels/snippets-panel";

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const { isOpen, selectedPanel } = useChromeState();
  const { setIsOpen } = useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);
  // We only support 'left' for now
  // We may add support for a bottom bar, but currently it forces the app to remount
  const panelLocation = "left";

  // sync sidebar
  useEffect(() => {
    if (!sidebarRef.current) {
      return;
    }

    const isCurrentlyCollapsed = sidebarRef.current.isCollapsed();
    if (isOpen && isCurrentlyCollapsed) {
      sidebarRef.current.expand();
    }
    if (!isOpen && !isCurrentlyCollapsed) {
      sidebarRef.current.collapse();
    }

    // Dispatch a resize event so widgets know to resize
    requestAnimationFrame(() => {
      // HACK: Unfortunately, we have to do this twice to make sure it the
      // panel is fully expanded before we dispatch the resize event
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event("resize"));
      });
    });
  }, [isOpen]);

  const appBody = (
    <Panel id="app" key={`app-${panelLocation}`} className="relative h-full">
      {children}
    </Panel>
  );

  const resizeHandle = (
    <PanelResizeHandle
      onDragging={(isDragging) => {
        if (!isDragging) {
          // Once the user is done dragging, dispatch a resize event
          window.dispatchEvent(new Event("resize"));
        }
      }}
      className={cn(
        "border-border no-print z-10",
        isOpen ? "resize-handle" : "resize-handle-collapsed",
        panelLocation === "left" ? "vertical" : "horizontal",
      )}
    />
  );

  const helpPaneBody = (
    <div className="flex flex-col h-full flex-1 overflow-hidden mr-[-4px]">
      <div className="p-3 border-b flex justify-between items-center">
        <div className="text-sm text-[var(--slate-11)] uppercase tracking-wide font-semibold flex-1">
          {selectedPanel}
        </div>
        <Button
          data-testid="close-helper-pane"
          className="m-0"
          size="xs"
          variant="text"
          onClick={() => setIsOpen(false)}
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>
      {selectedPanel === "files" && <FileExplorerPanel />}
      {selectedPanel === "errors" && <ErrorsPanel />}
      {selectedPanel === "variables" && <VariablePanel />}
      {selectedPanel === "dependencies" && <DependencyGraphPanel />}
      {selectedPanel === "outline" && <OutlinePanel />}
      {selectedPanel === "documentation" && <DocumentationPanel />}
      {selectedPanel === "snippets" && <SnippetsPanel />}
      {selectedPanel === "logs" && <LogsPanel />}
    </div>
  );

  const helperPane = (
    <Panel
      ref={sidebarRef}
      id="helper"
      key={`helper-${panelLocation}`}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "bg-white dark:bg-[var(--slate-1)] rounded-lg no-print shadow-mdNeutral",
        isOpen && "m-4",
      )}
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
      onCollapse={() => setIsOpen(false)}
      onExpand={() => setIsOpen(true)}
    >
      {panelLocation === "left" ? (
        <span className="flex flex-row h-full">
          {helpPaneBody} {resizeHandle}
        </span>
      ) : (
        <span>
          {resizeHandle} {helpPaneBody}
        </span>
      )}
    </Panel>
  );

  return (
    <div className="flex flex-col flex-1 overflow-hidden absolute inset-0">
      <PanelGroup
        key={panelLocation}
        autoSaveId={`marimo:chrome`}
        direction={panelLocation === "left" ? "horizontal" : "vertical"}
        storage={createStorage(panelLocation)}
      >
        {panelLocation === "left" ? helperPane : appBody}
        {panelLocation === "left" ? appBody : helperPane}
      </PanelGroup>
      <Footer />
    </div>
  );
};
