/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { MessageCircleQuestionIcon } from "lucide-react";
import { cn } from "@/utils/cn";
import { useChromeActions, useChromeState } from "../state";
import { Tooltip } from "@/components/ui/tooltip";
import { useAtomValue } from "jotai";
import { cellErrorCount } from "@/core/cells/cells";
import { FeedbackButton } from "../footer/feedback-button";
import { PANEL_ICONS, PanelType } from "../types";

export const Footer: React.FC = () => {
  const { selectedPanel } = useChromeState();
  const { openApplication } = useChromeActions();
  const errorCount = useAtomValue(cellErrorCount);

  const renderIcon = (type: PanelType, className?: string) => {
    const Icon = PANEL_ICONS[type];
    return <Icon className={cn("h-5 w-5", className)} />;
  };

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md px-4 border-t border-border select-none no-print text-sm shadow-[0_0_4px_1px_rgba(0,0,0,0.1)] z-50">
      <FooterItem
        tooltip="View errors"
        selected={selectedPanel === "errors"}
        onClick={() => openApplication("errors")}
      >
        {renderIcon("errors", errorCount > 0 ? "text-destructive" : "")}
        <span className="ml-1 font-mono mt-[0.125rem]">{errorCount}</span>
      </FooterItem>
      <FooterItem
        tooltip="View files"
        selected={selectedPanel === "files"}
        onClick={() => openApplication("files")}
      >
        {renderIcon("files")}
      </FooterItem>
      <FooterItem
        tooltip="Explore variables"
        selected={selectedPanel === "variables"}
        onClick={() => openApplication("variables")}
      >
        {renderIcon("variables")}
      </FooterItem>
      <FooterItem
        tooltip="Explore dependencies"
        selected={selectedPanel === "dependencies"}
        onClick={() => openApplication("dependencies")}
      >
        {renderIcon("dependencies")}
      </FooterItem>
      <FooterItem
        tooltip="View outline"
        selected={selectedPanel === "outline"}
        onClick={() => openApplication("outline")}
      >
        {renderIcon("outline")}
      </FooterItem>
      <FooterItem
        tooltip="View documentation"
        selected={selectedPanel === "documentation"}
        onClick={() => openApplication("documentation")}
      >
        {renderIcon("documentation")}
      </FooterItem>
      <FooterItem
        tooltip="Notebook logs"
        selected={selectedPanel === "logs"}
        onClick={() => openApplication("logs")}
      >
        {renderIcon("logs")}
      </FooterItem>

      <FeedbackButton>
        <FooterItem tooltip="Send feedback!" selected={false}>
          <MessageCircleQuestionIcon className="h-5 w-5" />
        </FooterItem>
      </FeedbackButton>

      <div className="mx-auto" />
    </footer>
  );
};

const FooterItem: React.FC<
  PropsWithChildren<
    {
      selected: boolean;
      tooltip: React.ReactNode;
    } & React.HTMLAttributes<HTMLDivElement>
  >
> = ({ children, tooltip, selected, className, ...rest }) => {
  return (
    <Tooltip content={tooltip} side="top">
      <div
        className={cn(
          "h-full flex items-center p-2 text-sm mx-[1px] shadow-inset font-mono cursor-pointer rounded",
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
