/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { MessageCircleQuestionIcon } from "lucide-react";
import type React from "react";
import type { PropsWithChildren } from "react";
import { useMemo } from "react";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { Tooltip } from "@/components/ui/tooltip";
import { notebookQueuedOrRunningCountAtom } from "@/core/cells/cells";
import { snippetsEnabledAtom } from "@/core/config/config";
import { cn } from "@/utils/cn";
import { FeedbackButton } from "../components/feedback-button";
import { panelLayoutAtom, useChromeActions, useChromeState } from "../state";
import { PANEL_MAP, PANELS, type PanelDescriptor } from "../types";

export const Sidebar: React.FC = () => {
  const { selectedPanel, selectedDeveloperPanelTab } = useChromeState();
  const { toggleApplication, setSelectedDeveloperPanelTab } =
    useChromeActions();
  const [panelLayout, setPanelLayout] = useAtom(panelLayoutAtom);
  const snippetsEnabled = useAtomValue(snippetsEnabledAtom);

  const renderIcon = ({ Icon }: PanelDescriptor, className?: string) => {
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  // Get panels available for sidebar context menu
  // Only show panels that are NOT in the developer panel
  const availableSidebarPanels = useMemo(() => {
    const devPanelIds = new Set(panelLayout.developerPanel);
    return PANELS.filter((p) => {
      if (p.hidden) {
        return false;
      }
      // Exclude panels that are in the developer panel
      if (devPanelIds.has(p.type)) {
        return false;
      }
      // Show defaultHidden panels only if enabled via config
      if (p.defaultHidden && p.type === "snippets" && !snippetsEnabled) {
        return false;
      }
      return true;
    });
  }, [panelLayout.developerPanel, snippetsEnabled]);

  // Convert current sidebar items to PanelDescriptors
  const sidebarItems = useMemo(() => {
    return panelLayout.sidebar.flatMap((id) => {
      const panel = PANEL_MAP.get(id);
      return panel ? [panel] : [];
    });
  }, [panelLayout.sidebar]);

  const handleSetSidebarItems = (items: PanelDescriptor[]) => {
    setPanelLayout((prev) => ({
      ...prev,
      sidebar: items.map((item) => item.type),
    }));
  };

  const handleReceive = (item: PanelDescriptor, fromListId: string) => {
    // Remove from the source list
    if (fromListId === "developer-panel") {
      setPanelLayout((prev) => ({
        ...prev,
        developerPanel: prev.developerPanel.filter((id) => id !== item.type),
      }));

      // If the moved item was selected in dev panel, select the first remaining item
      if (selectedDeveloperPanelTab === item.type) {
        const remainingDevPanels = panelLayout.developerPanel.filter(
          (id) => id !== item.type,
        );
        if (remainingDevPanels.length > 0) {
          setSelectedDeveloperPanelTab(remainingDevPanels[0]);
        }
      }
    }

    // Select the dropped item in sidebar
    toggleApplication(item.type);
  };

  return (
    <div className="h-full pt-4 pb-1 px-1 flex flex-col items-start text-muted-foreground text-md select-none no-print text-sm z-50 dark:bg-background print:hidden hide-on-fullscreen">
      <ReorderableList<PanelDescriptor>
        value={sidebarItems}
        setValue={handleSetSidebarItems}
        getKey={(p) => p.type}
        availableItems={availableSidebarPanels}
        crossListDrag={{
          dragType: "panels",
          listId: "sidebar",
          onReceive: handleReceive,
        }}
        getItemLabel={(panel) => (
          <span className="flex items-center gap-2">
            {renderIcon(panel, "h-4 w-4 text-muted-foreground")}
            {panel.label}
          </span>
        )}
        ariaLabel="Sidebar panels"
        className="flex flex-col gap-0"
        minItems={0}
        onAction={(panel) => toggleApplication(panel.type)}
        renderItem={(panel) => (
          <SidebarItem
            tooltip={panel.tooltip}
            selected={selectedPanel === panel.type}
          >
            {renderIcon(panel)}
          </SidebarItem>
        )}
      />
      <FeedbackButton>
        <SidebarItem tooltip="Send feedback!" selected={false}>
          <MessageCircleQuestionIcon className="h-5 w-5" />
        </SidebarItem>
      </FeedbackButton>
      <div className="flex-1" />
      <QueuedOrRunningStack />
    </div>
  );
};

const QueuedOrRunningStack = () => {
  const count = useAtomValue(notebookQueuedOrRunningCountAtom);
  return (
    <Tooltip
      content={
        count > 0 ? (
          <span>
            {count} cell{count > 1 ? "s" : ""} queued or running
          </span>
        ) : (
          "No cells queued or running"
        )
      }
      side="right"
      delayDuration={200}
    >
      <div className="flex flex-col-reverse gap-px overflow-hidden">
        {Array.from({ length: count }).map((_, index) => (
          <div
            key={index.toString()}
            className="shrink-0 h-1 w-2 bg-(--grass-6) border border-(--grass-7)"
          />
        ))}
      </div>
    </Tooltip>
  );
};

const SidebarItem: React.FC<
  PropsWithChildren<{
    selected: boolean;
    tooltip: React.ReactNode;
    className?: string;
    onClick?: () => void;
  }>
> = ({ children, tooltip, selected, className, onClick }) => {
  const itemClassName = cn(
    "flex items-center p-2 text-sm mx-px shadow-inset font-mono rounded",
    !selected && "hover:bg-(--sage-3)",
    selected && "bg-(--sage-4)",
    className,
  );

  // Render as div when not clickable (e.g., inside ReorderableList)
  // This avoids nested interactive elements which break react-aria's drag behavior
  const content = onClick ? (
    <button className={itemClassName} onClick={onClick}>
      {children}
    </button>
  ) : (
    <div className={itemClassName}>{children}</div>
  );

  return (
    <Tooltip content={tooltip} side="right" delayDuration={200}>
      {content}
    </Tooltip>
  );
};
