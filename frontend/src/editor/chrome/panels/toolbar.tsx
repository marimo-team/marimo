/* Copyright 2023 Marimo. All rights reserved. */
import React, { PropsWithChildren } from "react";
import { PanelType } from "../types";
import { XCircleIcon } from "lucide-react";
import { cn } from "../../../lib/utils";
import { Tooltip } from "@/components/ui/tooltip";

interface Props {
  selected: PanelType | undefined;
  onChange: (sidebar: PanelType) => void;
}

export const Toolbar: React.FC<Props> = ({ selected, onChange }) => {
  return (
    <div className="dark dark-theme flex flex-col h-full w-11 items-center p-4 dark gap-4 text-muted-foreground bg-background">
      <ToolbarButton
        selected={selected === "errors"}
        onClick={() => onChange("errors")}
        tooltip="Errors"
      >
        <XCircleIcon onClick={() => onChange("errors")} />
      </ToolbarButton>
    </div>
  );
};

const ToolbarButton: React.FC<
  PropsWithChildren<{
    selected: boolean;
    onClick: () => void;
    tooltip: string;
  }>
> = ({ selected, onClick, tooltip, children }) => {
  return (
    <Tooltip content={tooltip} side="right" usePortal={true}>
      <div
        className={cn(
          "pr-2 pl-2 py-2 cursor-pointer hover:text-foreground border-l-2 w-11",
          {
            "bg-slate-800 text-foreground shadow-[0px 0px 5px 1px rgba(0,0,0,0.5)] hover:border-border":
              selected,
            "hover:bg-slate-800 border-transparent": !selected,
          }
        )}
        onClick={onClick}
      >
        {children}
      </div>
    </Tooltip>
  );
};
