/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { MessageCircleQuestionIcon } from "lucide-react";
import type React from "react";
import type { PropsWithChildren } from "react";
import { useMemo } from "react";
import { ReorderableList } from "@/components/ui/reorderable-list";
import { Tooltip } from "@/components/ui/tooltip";
import { notebookQueuedOrRunningCountAtom } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import { FeedbackButton } from "../components/feedback-button";
import { sidebarOrderAtom, useChromeActions, useChromeState } from "../state";
import { PANEL_MAP, PANELS, type PanelDescriptor } from "../types";

export const Sidebar: React.FC = () => {
  const { selectedPanel } = useChromeState();
  const { toggleApplication } = useChromeActions();
  const [sidebarOrder, setSidebarOrder] = useAtom(sidebarOrderAtom);

  const renderIcon = ({ Icon }: PanelDescriptor, className?: string) => {
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  // Get all available sidebar panels
  const availableSidebarPanels = useMemo(
    () => PANELS.filter((p) => !p.hidden && p.position === "sidebar"),
    [],
  );

  const currentItems = sidebarOrder
    .map((id) => PANEL_MAP.get(id))
    .filter(Boolean);

  const handleSetValue = (panels: PanelDescriptor[]) => {
    setSidebarOrder(panels.map((p) => p.id));
  };

  return (
    <div className="h-full pt-4 pb-1 px-1 flex flex-col items-start text-muted-foreground text-md select-none no-print text-sm z-50 dark:bg-background print:hidden hide-on-fullscreen">
      <ReorderableList<PanelDescriptor>
        value={currentItems}
        setValue={handleSetValue}
        availableItems={availableSidebarPanels}
        getItemLabel={(panel) => (
          <span className="flex items-center gap-2 [">
            {renderIcon(panel, "h-4 w-4 text-muted-foreground")}
            {panel.tooltip}
          </span>
        )}
        ariaLabel="Reorderable sidebar panels"
        className="flex flex-col gap-0"
        renderItem={(panel) => {
          return (
            <SidebarItem
              tooltip={panel.tooltip}
              selected={selectedPanel === panel.id}
              onClick={() => toggleApplication(panel.id)}
            >
              {renderIcon(panel)}
            </SidebarItem>
          );
        }}
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
  PropsWithChildren<
    {
      selected: boolean;
      tooltip: React.ReactNode;
    } & React.HTMLAttributes<HTMLButtonElement>
  >
> = ({ children, tooltip, selected, className, ...rest }) => {
  return (
    <Tooltip content={tooltip} side="right" delayDuration={200}>
      <button
        className={cn(
          "flex items-center p-2 text-sm mx-px shadow-inset font-mono rounded",
          !selected && "hover:bg-(--sage-3)",
          selected && "bg-(--sage-4)",
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    </Tooltip>
  );
};
