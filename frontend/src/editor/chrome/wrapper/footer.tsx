/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import {
  PanelBottomIcon,
  PanelLeftIcon,
  VariableIcon,
  XCircleIcon,
} from "lucide-react";
import { useCells } from "@/core/state/cells";
import { cn } from "@/lib/utils";
import { useChromeActions, useChromeState } from "../state";

export const Footer: React.FC = () => {
  const { selectedPanel, panelLocation } = useChromeState();
  const { openApplication, changePanelLocation } = useChromeActions();

  const cells = useCells();
  const errors = cells.present
    .map((cell) =>
      cell.output?.mimetype === "application/vnd.marimo+error"
        ? {
            output: cell.output,
            cellId: cell.key,
          }
        : null
    )
    .filter(Boolean);

  return (
    <footer className="h-6 bg-[var(--sage-3)] flex items-center text-muted-foreground text-md px-6 border-t border-border select-none">
      <FooterItem
        selected={selectedPanel === "errors"}
        onClick={() => openApplication("errors")}
      >
        <XCircleIcon
          className={cn("h-4 w-4 mr-1", {
            "text-destructive": errors.length > 0,
          })}
        />
        {errors.length}
      </FooterItem>
      <FooterItem
        selected={selectedPanel === "variables"}
        onClick={() => openApplication("variables")}
      >
        <VariableIcon className={cn("h-4 w-4 mr-1")} />
        {errors.length}
      </FooterItem>
      <div className="mx-auto" />
      <FooterItem
        selected={panelLocation === "left"}
        onClick={() => changePanelLocation("left")}
      >
        <PanelLeftIcon className="h-4 w-4" />
      </FooterItem>
      <FooterItem
        selected={panelLocation === "bottom"}
        onClick={() => changePanelLocation("bottom")}
      >
        <PanelBottomIcon className="h-4 w-4" />
      </FooterItem>
    </footer>
  );
};

const FooterItem: React.FC<
  PropsWithChildren<{
    selected: boolean;
    onClick: () => void;
  }>
> = ({ children, onClick, selected }) => {
  return (
    <div
      className={cn(
        "h-full flex items-center px-2 shadow-inset font-mono cursor-pointer",
        !selected && "hover:bg-[var(--sage-4)]",
        selected && "bg-[var(--sage-6)]"
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
};
