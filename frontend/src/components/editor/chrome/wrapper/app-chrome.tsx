/* Copyright 2026 Marimo. All rights reserved. */
import React, {
  type PropsWithChildren,
  Suspense,
  useEffect,
  useMemo,
} from "react";
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
import { useAtom, useAtomValue } from "jotai";
import { XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LazyMount } from "@/components/utils/lazy-mount";
import { cellErrorCount } from "@/core/cells/cells";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { cn } from "@/utils/cn";
import { ErrorBoundary } from "../../boundary/ErrorBoundary";
import { ContextAwarePanel } from "../panels/context-aware-panel/context-aware-panel";
import { PanelSectionProvider } from "../panels/panel-context";
import { panelLayoutAtom, useChromeActions, useChromeState } from "../state";
import {
  isPanelHidden,
  PANEL_MAP,
  PANELS,
  type PanelDescriptor,
} from "../types";
import { BackendConnectionStatus } from "./footer-items/backend-status";
import { PanelsWrapper } from "./panels";
import { PendingAICells } from "./pending-ai-cells";
import { useAiPanelTab } from "./useAiPanel";
import { useDependencyPanelTab } from "./useDependencyPanelTab";
import { handleDragging } from "./utils";

const LazyTerminal = React.lazy(() => import("@/components/terminal/terminal"));
const LazyChatPanel = React.lazy(() => import("@/components/chat/chat-panel"));
const LazyAgentPanel = React.lazy(
  () => import("@/components/chat/acp/agent-panel"),
);
const LazyDependencyGraphPanel = React.lazy(
  () => import("@/components/editor/chrome/panels/dependency-graph-panel"),
);
const LazySessionPanel = React.lazy(() => import("../panels/session-panel"));
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
const LazyCachePanel = React.lazy(() => import("../panels/cache-panel"));

export const AppChrome: React.FC<PropsWithChildren> = ({ children }) => {
  const {
    isSidebarOpen,
    isDeveloperPanelOpen,
    selectedPanel,
    selectedDeveloperPanelTab,
  } = useChromeState();
  const { setIsSidebarOpen, setIsDeveloperPanelOpen, openApplication } =
    useChromeActions();
  const sidebarRef = React.useRef<ImperativePanelHandle>(null);
  const developerPanelRef = React.useRef<ImperativePanelHandle>(null);
  const { aiPanelTab, setAiPanelTab } = useAiPanelTab();
  const { dependencyPanelTab, setDependencyPanelTab } = useDependencyPanelTab();
  const errorCount = useAtomValue(cellErrorCount);
  const [panelLayout, setPanelLayout] = useAtom(panelLayoutAtom);
  // Subscribe to capabilities to re-render when they change (e.g., terminal capability)
  const capabilities = useAtomValue(capabilitiesAtom);

  // Convert current developer panel items to PanelDescriptors
  // Filter out hidden panels (e.g., terminal when capability is not available)
  const devPanelItems = useMemo(() => {
    return panelLayout.developerPanel.flatMap((id) => {
      const panel = PANEL_MAP.get(id);
      if (!panel || isPanelHidden(panel, capabilities)) {
        return [];
      }
      return [panel];
    });
  }, [panelLayout.developerPanel, capabilities]);

  const handleSetDevPanelItems = (items: PanelDescriptor[]) => {
    setPanelLayout((prev) => ({
      ...prev,
      developerPanel: items.map((item) => item.type),
    }));
  };

  const handleDevPanelReceive = (item: PanelDescriptor, fromListId: string) => {
    // Remove from the source list
    if (fromListId === "sidebar") {
      setPanelLayout((prev) => ({
        ...prev,
        sidebar: prev.sidebar.filter((id) => id !== item.type),
      }));

      // If the moved item was selected in sidebar, select the first remaining item
      if (selectedPanel === item.type) {
        const remainingSidebar = panelLayout.sidebar.filter(
          (id) => id !== item.type,
        );
        if (remainingSidebar.length > 0) {
          openApplication(remainingSidebar[0]);
        }
      }
    }

    // Select the dropped item in developer panel
    openApplication(item.type);
  };

  // Get panels available for developer panel context menu
  // Only show panels that are NOT in the sidebar
  const availableDevPanels = useMemo(() => {
    const sidebarIds = new Set(panelLayout.sidebar);
    return PANELS.filter((p) => {
      if (isPanelHidden(p, capabilities)) {
        return false;
      }
      // Exclude panels that are in the sidebar
      if (sidebarIds.has(p.type)) {
        return false;
      }
      return true;
    });
  }, [panelLayout.sidebar, capabilities]);

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

  // sync panel
  useEffect(() => {
    if (!developerPanelRef.current) {
      return;
    }

    const isCurrentlyCollapsed = developerPanelRef.current.isCollapsed();
    if (isDeveloperPanelOpen && isCurrentlyCollapsed) {
      developerPanelRef.current.expand();
    }
    if (!isDeveloperPanelOpen && !isCurrentlyCollapsed) {
      developerPanelRef.current.collapse();
    }

    // Dispatch a resize event so widgets know to resize
    requestAnimationFrame(() => {
      // HACK: Unfortunately, we have to do this twice to make sure it the
      // panel is fully expanded before we dispatch the resize event
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event("resize"));
      });
    });
  }, [isDeveloperPanelOpen]);

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

  const panelResizeHandle = (
    <PanelResizeHandle
      onDragging={handleDragging}
      className={cn(
        "border-border no-print z-20",
        isDeveloperPanelOpen ? "resize-handle" : "resize-handle-collapsed",
        "horizontal",
      )}
    />
  );

  const agentsEnabled = getFeatureFlag("external_agents");

  const renderAiPanel = () => {
    if (agentsEnabled && aiPanelTab === "agents") {
      return <LazyAgentPanel />;
    }
    return <LazyChatPanel />;
  };

  const helpPaneBody = (
    <ErrorBoundary>
      <PanelSectionProvider value="sidebar">
        <div className="flex flex-col h-full flex-1 overflow-hidden mr-[-4px]">
          <div className="p-3 border-b flex justify-between items-center">
            {selectedPanel === "dependencies" ? (
              <div className="flex items-center justify-between flex-1">
                <span className="text-sm text-(--slate-11) uppercase tracking-wide font-semibold">
                  Dependencies
                </span>
                <Tabs
                  value={dependencyPanelTab}
                  onValueChange={(value) => {
                    if (value === "minimap" || value === "graph") {
                      setDependencyPanelTab(value);
                    }
                  }}
                >
                  <TabsList>
                    <TabsTrigger
                      value="minimap"
                      className="py-0.5 text-xs uppercase tracking-wide font-bold"
                    >
                      Minimap
                    </TabsTrigger>
                    <TabsTrigger
                      value="graph"
                      className="py-0.5 text-xs uppercase tracking-wide font-bold"
                    >
                      Graph
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            ) : selectedPanel === "ai" && agentsEnabled ? (
              <Tabs
                value={aiPanelTab}
                onValueChange={(value) => {
                  if (value === "chat" || value === "agents") {
                    setAiPanelTab(value);
                  }
                }}
              >
                <TabsList>
                  <TabsTrigger
                    value="chat"
                    className="py-0.5 text-xs uppercase tracking-wide font-bold"
                  >
                    Chat
                  </TabsTrigger>
                  <TabsTrigger
                    value="agents"
                    className="py-0.5 text-xs uppercase tracking-wide font-bold"
                  >
                    Agents
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            ) : (
              <span className="text-sm text-(--slate-11) uppercase tracking-wide font-semibold flex-1">
                {selectedPanel}
              </span>
            )}
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
              {selectedPanel === "variables" && <LazySessionPanel />}
              {selectedPanel === "dependencies" && <LazyDependencyGraphPanel />}
              {selectedPanel === "packages" && <LazyPackagesPanel />}
              {selectedPanel === "outline" && <LazyOutlinePanel />}
              {selectedPanel === "documentation" && <LazyDocumentationPanel />}
              {selectedPanel === "snippets" && <LazySnippetsPanel />}
              {selectedPanel === "ai" && renderAiPanel()}
              {selectedPanel === "errors" && <LazyErrorsPanel />}
              {selectedPanel === "scratchpad" && <LazyScratchpadPanel />}
              {selectedPanel === "tracing" && <LazyTracingPanel />}
              {selectedPanel === "secrets" && <LazySecretsPanel />}
              {selectedPanel === "logs" && <LazyLogsPanel />}
              {selectedPanel === "terminal" && (
                <LazyTerminal
                  visible={isSidebarOpen}
                  onClose={() => setIsSidebarOpen(false)}
                />
              )}
              {selectedPanel === "cache" && <LazyCachePanel />}
            </TooltipProvider>
          </Suspense>
        </div>
      </PanelSectionProvider>
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

  const bottomPanel = (
    <Panel
      ref={developerPanelRef}
      // This cannot by dynamic and must be constant
      // so that the size is preserved between page loads
      id="app-chrome-panel"
      data-testid="panel"
      key={"panel"}
      collapsedSize={0}
      collapsible={true}
      className={cn(
        "dark:bg-(--slate-1) no-print print:hidden hide-on-fullscreen",
        isDeveloperPanelOpen && "border-t",
      )}
      minSize={10}
      // We can't make the default size greater than 0, otherwise it will start open
      defaultSize={0}
      maxSize={75}
      onResize={(size, prevSize) => {
        // This means it started closed and is opening for the first time
        if (prevSize === 0 && size === 10) {
          developerPanelRef.current?.resize(30);
        }
      }}
      onCollapse={() => setIsDeveloperPanelOpen(false)}
      onExpand={() => setIsDeveloperPanelOpen(true)}
    >
      {panelResizeHandle}
      <div className="flex flex-col h-full">
        {/* Panel header with tabs */}
        <div className="flex items-center justify-between border-b px-2 h-8 bg-background shrink-0">
          <ReorderableList<PanelDescriptor>
            value={devPanelItems}
            setValue={handleSetDevPanelItems}
            getKey={(p) => p.type}
            availableItems={availableDevPanels}
            crossListDrag={{
              dragType: "panels",
              listId: "developer-panel",
              onReceive: handleDevPanelReceive,
            }}
            getItemLabel={(panel) => (
              <span className="flex items-center gap-2">
                <panel.Icon className="w-4 h-4 text-muted-foreground" />
                {panel.label}
              </span>
            )}
            ariaLabel="Developer panel tabs"
            className="flex flex-row gap-1"
            minItems={0}
            onAction={(panel) => openApplication(panel.type)}
            renderItem={(panel) => (
              <div
                className={cn(
                  "text-sm flex gap-2 px-2 pt-1 pb-0.5 items-center leading-none rounded-sm cursor-pointer",
                  selectedDeveloperPanelTab === panel.type
                    ? "bg-muted"
                    : "hover:bg-muted/50",
                )}
              >
                <panel.Icon
                  className={cn(
                    "w-4 h-4",
                    panel.type === "errors" &&
                      errorCount > 0 &&
                      "text-destructive",
                  )}
                />
                {panel.label}
              </div>
            )}
          />
          <div className="border-l border-border h-4 mx-1" />
          <BackendConnectionStatus />
          <div className="flex-1" />
          <Button
            size="xs"
            variant="text"
            onClick={() => setIsDeveloperPanelOpen(false)}
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </div>
        {/* Panel content */}
        <Suspense fallback={<div />}>
          <PanelSectionProvider value="developer-panel">
            <div className="flex-1 overflow-hidden">
              {selectedDeveloperPanelTab === "files" && (
                <LazyFileExplorerPanel />
              )}
              {selectedDeveloperPanelTab === "variables" && (
                <LazySessionPanel />
              )}
              {selectedDeveloperPanelTab === "dependencies" && (
                <LazyDependencyGraphPanel />
              )}
              {selectedDeveloperPanelTab === "packages" && (
                <LazyPackagesPanel />
              )}
              {selectedDeveloperPanelTab === "outline" && <LazyOutlinePanel />}
              {selectedDeveloperPanelTab === "documentation" && (
                <LazyDocumentationPanel />
              )}
              {selectedDeveloperPanelTab === "snippets" && (
                <LazySnippetsPanel />
              )}
              {selectedDeveloperPanelTab === "ai" && renderAiPanel()}
              {selectedDeveloperPanelTab === "errors" && <LazyErrorsPanel />}
              {selectedDeveloperPanelTab === "scratchpad" && (
                <LazyScratchpadPanel />
              )}
              {selectedDeveloperPanelTab === "tracing" && <LazyTracingPanel />}
              {selectedDeveloperPanelTab === "secrets" && <LazySecretsPanel />}
              {selectedDeveloperPanelTab === "logs" && <LazyLogsPanel />}
              {/* LazyMount needed for Terminal to avoid spurious connection */}
              {selectedDeveloperPanelTab === "terminal" && (
                <LazyMount isOpen={isDeveloperPanelOpen}>
                  <LazyTerminal
                    visible={isDeveloperPanelOpen}
                    onClose={() => setIsDeveloperPanelOpen(false)}
                  />
                </LazyMount>
              )}
              {selectedDeveloperPanelTab === "cache" && <LazyCachePanel />}
            </div>
          </PanelSectionProvider>
        </Suspense>
      </div>
    </Panel>
  );

  return (
    <PanelsWrapper>
      <PanelGroup autoSaveId="marimo:chrome:v1:l2" direction={"horizontal"}>
        <TooltipProvider>
          <Sidebar />
        </TooltipProvider>
        {helperPanel}
        <Panel
          id="app-chrome-body"
          className={cn(isDeveloperPanelOpen && !isSidebarOpen && "border-l")}
        >
          <PanelGroup autoSaveId="marimo:chrome:v1:l1" direction="vertical">
            {appBodyPanel}
            {bottomPanel}
          </PanelGroup>
        </Panel>
        <ContextAwarePanel />
      </PanelGroup>
      <PendingAICells />
      <ErrorBoundary>
        <TooltipProvider>
          <Footer />
        </TooltipProvider>
      </ErrorBoundary>
    </PanelsWrapper>
  );
};
