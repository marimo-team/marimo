/* Copyright 2024 Marimo. All rights reserved. */
import React, { type PropsWithChildren, useEffect, Suspense } from "react";
import {
  PanelGroup,
  Panel,
  PanelResizeHandle,
  type ImperativePanelHandle,
} from "react-resizable-panels";
import { Footer } from "./footer";
import { Sidebar } from "./sidebar";
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
import { ErrorBoundary } from "../../boundary/ErrorBoundary";
import { DataSourcesPanel } from "../panels/datasources-panel";
import { LazyMount } from "@/components/utils/lazy-mount";
import { ScratchpadPanel } from "../panels/scratchpad-panel";
import { IfCapability } from "@/core/config/if-capability";

const LazyTerminal = React.lazy(() => import("@/components/terminal/terminal"));

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const { isSidebarOpen, isTerminalOpen, selectedPanel } = useChromeState();
  const { setIsSidebarOpen, setIsTerminalOpen } = useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);
  const terminalRef = React.useRef<ImperativePanelHandle>(null);

  // sync sidebar
  useEffect(() => {
    if (!sidebarRef.current) {
      return;
    }

    const isCurrentlyCollapsed = sidebarRef.current.isCollapsed();
    if (isSidebarOpen && isCurrentlyCollapsed) {
      sidebarRef.current.expand();
    }
    if (!isSidebarOpen && !isCurrentlyCollapsed) {
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
  }, [isSidebarOpen]);

  // sync terminal
  useEffect(() => {
    if (!terminalRef.current) {
      return;
    }

    const isCurrentlyCollapsed = terminalRef.current.isCollapsed();
    if (isTerminalOpen && isCurrentlyCollapsed) {
      terminalRef.current.expand();
    }
    if (!isTerminalOpen && !isCurrentlyCollapsed) {
      terminalRef.current.collapse();
    }

    // Dispatch a resize event so widgets know to resize
    requestAnimationFrame(() => {
      // HACK: Unfortunately, we have to do this twice to make sure it the
      // panel is fully expanded before we dispatch the resize event
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event("resize"));
      });
    });
  }, [isTerminalOpen]);

  const appBodyPanel = (
    <Panel id="app" key="app" className="relative h-full">
      <Suspense>{children}</Suspense>
    </Panel>
  );

  const handleDragging = (isDragging: boolean) => {
    if (!isDragging) {
      // Once the user is done dragging, dispatch a resize event
      window.dispatchEvent(new Event("resize"));
    }
  };

  const helperResizeHandle = (
    <PanelResizeHandle
      onDragging={handleDragging}
      className={cn(
        "border-border no-print z-10",
        isSidebarOpen ? "resize-handle" : "resize-handle-collapsed",
        "vertical",
      )}
    />
  );

  const terminalResizeHandle = (
    <PanelResizeHandle
      onDragging={handleDragging}
      className={cn(
        "border-border no-print z-20",
        isTerminalOpen ? "resize-handle" : "resize-handle-collapsed",
        "horizontal",
      )}
    />
  );

  const helpPaneBody = (
    <ErrorBoundary>
      <Suspense>
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
              onClick={() => setIsSidebarOpen(false)}
            >
              <XIcon className="w-4 h-4" />
            </Button>
          </div>
          {selectedPanel === "files" && <FileExplorerPanel />}
          {selectedPanel === "errors" && <ErrorsPanel />}
          {selectedPanel === "variables" && <VariablePanel />}
          {selectedPanel === "dependencies" && <DependencyGraphPanel />}
          {selectedPanel === "outline" && <OutlinePanel />}
          {selectedPanel === "datasources" && <DataSourcesPanel />}
          {selectedPanel === "documentation" && <DocumentationPanel />}
          {selectedPanel === "snippets" && <SnippetsPanel />}
          {selectedPanel === "scratchpad" && <ScratchpadPanel />}
          {selectedPanel === "logs" && <LogsPanel />}
        </div>
      </Suspense>
    </ErrorBoundary>
  );

  const helperPanel = (
    <Panel
      ref={sidebarRef}
      id="helper"
      key={"helper"}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "dark:bg-[var(--slate-1)] no-print print:hidden",
        isSidebarOpen && "border-r border-l border-[var(--slate-7)]",
      )}
      minSize={10}
      // We can't make the default size greater than 0, otherwise it will start open
      defaultSize={0}
      maxSize={75}
      onResize={(size, prevSize) => {
        // This means it started closed and is opening for the first time
        if (prevSize === 0 && size === 10) {
          sidebarRef.current?.resize(30);
        }
      }}
      onCollapse={() => setIsSidebarOpen(false)}
      onExpand={() => setIsSidebarOpen(true)}
    >
      <span className="flex flex-row h-full">
        {helpPaneBody} {helperResizeHandle}
      </span>
    </Panel>
  );

  const terminalPanel = (
    <Panel
      ref={terminalRef}
      id="terminal"
      key={"terminal"}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "dark:bg-[var(--slate-1)] no-print print:hidden",
        isTerminalOpen && "border-[var(--slate-7)]",
      )}
      minSize={10}
      // We can't make the default size greater than 0, otherwise it will start open
      defaultSize={0}
      maxSize={75}
      onResize={(size, prevSize) => {
        // This means it started closed and is opening for the first time
        if (prevSize === 0 && size === 10) {
          terminalRef.current?.resize(30);
        }
      }}
      onCollapse={() => setIsTerminalOpen(false)}
      onExpand={() => setIsTerminalOpen(true)}
    >
      {terminalResizeHandle}
      <LazyMount isOpen={isTerminalOpen}>
        <LazyTerminal
          visible={isTerminalOpen}
          onClose={() => setIsTerminalOpen(false)}
        />
      </LazyMount>
    </Panel>
  );

  return (
    <div className="flex flex-col flex-1 overflow-hidden absolute inset-0 print:relative">
      <PanelGroup
        autoSaveId="marimo:chrome:v1:l2"
        direction={"horizontal"}
        storage={createStorage("left")}
      >
        <Sidebar />
        {helperPanel}
        <Panel>
          <PanelGroup autoSaveId="marimo:chrome:v1:l1" direction="vertical">
            {appBodyPanel}
            <IfCapability capability="terminal">{terminalPanel}</IfCapability>
          </PanelGroup>
        </Panel>
      </PanelGroup>
      <ErrorBoundary>
        <Footer />
      </ErrorBoundary>
    </div>
  );
};
