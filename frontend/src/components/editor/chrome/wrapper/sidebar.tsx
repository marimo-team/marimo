/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { MessageCircleQuestionIcon } from "lucide-react";
import { cn } from "@/utils/cn";
import { useChromeActions, useChromeState } from "../state";
import { Tooltip } from "@/components/ui/tooltip";
import { FeedbackButton } from "../components/feedback-button";
import { PANEL_ICONS, PanelType } from "../types";

export const Sidebar: React.FC = () => {
  const { selectedPanel } = useChromeState();
  const { openApplication } = useChromeActions();

  const renderIcon = (type: PanelType, className?: string) => {
    const Icon = PANEL_ICONS[type];
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  return (
    <div className="h-full py-4 px-1 flex flex-col items-start text-muted-foreground text-md select-none no-print text-sm z-50">
      <SidebarItem
        tooltip="View files"
        selected={selectedPanel === "files"}
        onClick={() => openApplication("files")}
      >
        {renderIcon("files")}
      </SidebarItem>
      <SidebarItem
        tooltip="Explore variables"
        selected={selectedPanel === "variables"}
        onClick={() => openApplication("variables")}
      >
        {renderIcon("variables")}
      </SidebarItem>
      <SidebarItem
        tooltip="Explore dependencies"
        selected={selectedPanel === "dependencies"}
        onClick={() => openApplication("dependencies")}
      >
        {renderIcon("dependencies")}
      </SidebarItem>
      <SidebarItem
        tooltip="View outline"
        selected={selectedPanel === "outline"}
        onClick={() => openApplication("outline")}
      >
        {renderIcon("outline")}
      </SidebarItem>
      <SidebarItem
        tooltip="View live docs"
        selected={selectedPanel === "documentation"}
        onClick={() => openApplication("documentation")}
      >
        {renderIcon("documentation")}
      </SidebarItem>
      <SidebarItem
        tooltip="Notebook logs"
        selected={selectedPanel === "logs"}
        onClick={() => openApplication("logs")}
      >
        {renderIcon("logs")}
      </SidebarItem>
      <SidebarItem
        tooltip="Snippets"
        selected={selectedPanel === "snippets"}
        onClick={() => openApplication("snippets")}
      >
        {renderIcon("snippets")}
      </SidebarItem>

      <FeedbackButton>
        <SidebarItem tooltip="Send feedback!" selected={false}>
          <MessageCircleQuestionIcon className="h-5 w-5" />
        </SidebarItem>
      </FeedbackButton>
    </div>
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
