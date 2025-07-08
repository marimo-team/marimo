/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { MessageCircleQuestionIcon } from "lucide-react";
import type React from "react";
import type { PropsWithChildren } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { notebookQueuedOrRunningCountAtom } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import { FeedbackButton } from "../components/feedback-button";
import { useChromeActions, useChromeState } from "../state";
import { PANELS, type PanelDescriptor } from "../types";

export const Sidebar: React.FC = () => {
  const { selectedPanel } = useChromeState();
  const { toggleApplication } = useChromeActions();

  const renderIcon = ({ Icon }: PanelDescriptor, className?: string) => {
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  const sidebarItems = PANELS.filter(
    (p) => !p.hidden && p.position === "sidebar",
  );

  return (
    <div className="h-full pt-4 pb-1 px-1 flex flex-col items-start text-muted-foreground text-md select-none no-print text-sm z-50 dark:bg-background print:hidden hide-on-fullscreen">
      {sidebarItems.map((p) => (
        <SidebarItem
          key={p.type}
          tooltip={p.tooltip}
          selected={selectedPanel === p.type}
          onClick={() => toggleApplication(p.type)}
        >
          {renderIcon(p)}
        </SidebarItem>
      ))}
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
      <div className="flex flex-col-reverse gap-[1px] overflow-hidden">
        {Array.from({ length: count }).map((_, index) => (
          <div
            key={index.toString()}
            className="flex-shrink-0 h-1 w-2 bg-[var(--grass-6)] border border-[var(--grass-7)]"
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
    } & React.HTMLAttributes<HTMLDivElement>
  >
> = ({ children, tooltip, selected, className, ...rest }) => {
  return (
    <Tooltip content={tooltip} side="right" delayDuration={200}>
      <div
        className={cn(
          "flex items-center p-2 text-sm mx-[1px] shadow-inset font-mono cursor-pointer rounded",
          !selected && "hover:bg-[var(--sage-3)]",
          selected && "bg-[var(--sage-4)]",
          className,
        )}
        {...rest}
      >
        {children}
      </div>
    </Tooltip>
  );
};
