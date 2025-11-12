/* Copyright 2024 Marimo. All rights reserved. */
import React, { type PropsWithChildren, Suspense, useEffect } from "react";
import {
  type ImperativePanelHandle,
  Panel,
  PanelGroup,
  PanelResizeHandle,
} from "react-resizable-panels";
import { Footer } from "./footer";
import { Sidebar } from "./sidebar";
import "./app-chrome.css";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LazyMount } from "@/components/utils/lazy-mount";
import { IfCapability } from "@/core/config/if-capability";
import { cn } from "@/utils/cn";
import { ErrorBoundary } from "../../boundary/ErrorBoundary";
import { ContextAwarePanel } from "../panels/context-aware-panel/context-aware-panel";
import { useChromeActions, useChromeState } from "../state";
import { Minimap } from "./minimap";
import { PanelsWrapper } from "./panels";
import { PendingAICells } from "./pending-ai-cells";
import { handleDragging } from "./utils";

const LazyTerminal = React.lazy(() => import("@/components/terminal/terminal"));
const LazyChatPanel = React.lazy(() => import("@/components/chat/chat-panel"));
const LazyAgentPanel = React.lazy(
  () => import("@/components/chat/acp/agent-panel"),
);
const LazyDependencyGraphPanel = React.lazy(
  () => import("@/components/editor/chrome/panels/dependency-graph-panel"),
);
const LazyDataSourcesPanel = React.lazy(
  () => import("../panels/datasources-panel"),
);
const LazyDocumentationPanel = React.lazy(
  () => import("../panels/documentation-panel"),
);
const LazyErrorsPanel = React.lazy(() => import("../panels/error-panel"));
const LazyFileExplorerPanel = React.lazy(
  () => import("../panels/file-explorer-panel"),
);
const LazyLogsPanel = React.lazy(() => import("../panels/logs-panel"));
const LazyOutlinePanel = React.lazy(() => import("../panels/outline-panel"));
const LazyPackagesPanel = React.lazy(() => import("../panels/packages-panel"));
const LazyScratchpadPanel = React.lazy(
  () => import("../panels/scratchpad-panel"),
);
const LazySecretsPanel = React.lazy(() => import("../panels/secrets-panel"));
const LazySnippetsPanel = React.lazy(() => import("../panels/snippets-panel"));
const LazyTracingPanel = React.lazy(() => import("../panels/tracing-panel"));
const LazyVariablePanel = React.lazy(() => import("../panels/variable-panel"));
const LazyCachePanel = React.lazy(() => import("../panels/cache-panel"));

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
      <div className="flex flex-col h-full flex-1 overflow-hidden mr-[-4px]">
        <div className="p-3 border-b flex justify-between items-center">
          <div className="text-sm text-(--slate-11) uppercase tracking-wide font-semibold flex-1">
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
        <Suspense>
          <TooltipProvider>
            {selectedPanel === "files" && <LazyFileExplorerPanel />}
            {selectedPanel === "errors" && <LazyErrorsPanel />}
            {selectedPanel === "variables" && <LazyVariablePanel />}
            {selectedPanel === "dependencies" && <LazyDependencyGraphPanel />}
            {selectedPanel === "packages" && <LazyPackagesPanel />}
            {selectedPanel === "outline" && <LazyOutlinePanel />}
            {selectedPanel === "datasources" && <LazyDataSourcesPanel />}
            {selectedPanel === "documentation" && <LazyDocumentationPanel />}
            {selectedPanel === "snippets" && <LazySnippetsPanel />}
            {selectedPanel === "scratchpad" && <LazyScratchpadPanel />}
            {selectedPanel === "chat" && <LazyChatPanel />}
            {selectedPanel === "agents" && <LazyAgentPanel />}
            {selectedPanel === "logs" && <LazyLogsPanel />}
            {selectedPanel === "tracing" && <LazyTracingPanel />}
            {selectedPanel === "secrets" && <LazySecretsPanel />}
            {selectedPanel === "cache" && <LazyCachePanel />}
          </TooltipProvider>
        </Suspense>
      </div>
    </ErrorBoundary>
  );

  const helperPanel = (
    <Panel
      ref={sidebarRef}
      // This cannot by dynamic and must be constant
      // so that the size is preserved between page loads
      id="app-chrome-sidebar"
      data-testid="helper"
      key={"helper"}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "dark:bg-(--slate-1) no-print print:hidden hide-on-fullscreen",
        isSidebarOpen && "border-r border-l border-(--slate-7)",
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
      // This cannot by dynamic and must be constant
      // so that the size is preserved between page loads
      id="app-chrome-terminal"
      data-testid="terminal"
      key={"terminal"}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "dark:bg-(--slate-1) no-print print:hidden hide-on-fullscreen",
        isTerminalOpen && "border-(--slate-7)",
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
        <Suspense fallback={<div />}>
          <LazyTerminal
            visible={isTerminalOpen}
            onClose={() => setIsTerminalOpen(false)}
          />
        </Suspense>
      </LazyMount>
    </Panel>
  );

  return (
    <PanelsWrapper>
      <PanelGroup autoSaveId="marimo:chrome:v1:l2" direction={"horizontal"}>
        <TooltipProvider>
          <Sidebar />
        </TooltipProvider>
        {helperPanel}
        <Panel id="app-chrome-body">
          <PanelGroup autoSaveId="marimo:chrome:v1:l1" direction="vertical">
            {appBodyPanel}
            <IfCapability capability="terminal">{terminalPanel}</IfCapability>
          </PanelGroup>
        </Panel>
        <ContextAwarePanel />
      </PanelGroup>
      <Minimap />
      <PendingAICells />
      <ErrorBoundary>
        <TooltipProvider>
          <Footer />
        </TooltipProvider>
      </ErrorBoundary>
    </PanelsWrapper>
  );
};
