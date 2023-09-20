/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { PanelBottomIcon, PanelLeftIcon, VariableIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChromeActions, useChromeState } from "../state";
import { Tooltip } from "@/components/ui/tooltip";

export const Footer: React.FC = () => {
  const { selectedPanel, panelLocation } = useChromeState();
  const { openApplication, changePanelLocation } = useChromeActions();

  return (
    <footer className="h-10 py-2 bg-background flex items-center text-muted-foreground text-md px-6 border-t border-border select-none no-print">
      {/* <FooterItem
        selected={selectedPanel === "errors"}
        onClick={() => openApplication("errors")}
      >
        <XCircleIcon
          className={cn("h-4 w-4 mr-1", {
            "text-destructive": errors.length > 0,
          })}
        />
        {errors.length}
      </FooterItem> */}
      <FooterItem
        tooltip="Explore variables"
        selected={selectedPanel === "variables"}
        onClick={() => openApplication("variables")}
      >
        <VariableIcon className={cn("h-4 w-4")} />
      </FooterItem>
      <div className="mx-auto" />
      <FooterItem
        tooltip="Move panel to the left"
        selected={panelLocation === "left"}
        onClick={() => changePanelLocation("left")}
      >
        <PanelLeftIcon className="h-4 w-4" />
      </FooterItem>
      <FooterItem
        tooltip="Move panel to the bottom"
        selected={panelLocation === "bottom"}
        onClick={() => changePanelLocation("bottom")}
      >
        <PanelBottomIcon className="h-4 w-4" />
      </FooterItem>
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
          className
        )}
        {...rest}
      >
        {children}
      </div>
    </Tooltip>
  );
};
