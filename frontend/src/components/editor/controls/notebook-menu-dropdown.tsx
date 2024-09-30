/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/editor/inputs/Inputs";
import { MenuIcon } from "lucide-react";
import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MinimalShortcut } from "../../shortcuts/renderShortcut";
import { useNotebookActions } from "../actions/useNotebookActions";
import type { ActionButton } from "../actions/types";
import { getMarimoVersion } from "@/core/dom/marimo-tag";
import { Tooltip } from "@/components/ui/tooltip";

export const NotebookMenuDropdown: React.FC = () => {
  const actions = useNotebookActions();

  const button = (
    <Button
      aria-label="Config"
      shape="circle"
      size="small"
      className="h-[27px] w-[27px]"
      data-testid="notebook-menu-dropdown"
      color="hint-green"
    >
      <MenuIcon strokeWidth={1.8} />
    </Button>
  );

  const renderLabel = (action: ActionButton) => {
    return (
      <>
        {action.icon && <span className="flex-0 mr-2">{action.icon}</span>}
        <span className="flex-1">{action.labelElement || action.label}</span>
        {action.hotkey && (
          <MinimalShortcut shortcut={action.hotkey} className="ml-4" />
        )}
        {action.rightElement}
      </>
    );
  };

  const renderLeafAction = (action: ActionButton) => {
    const item = (
      <DropdownMenuItem
        key={action.label}
        variant={action.variant}
        disabled={action.disabled}
        onSelect={(evt) => action.handle(evt)}
        data-testid={`notebook-menu-dropdown-${action.label}`}
      >
        {renderLabel(action)}
      </DropdownMenuItem>
    );

    if (action.tooltip) {
      return (
        <Tooltip
          content={action.tooltip}
          key={action.label}
          side="left"
          delayDuration={100}
        >
          <span>{item}</span>
        </Tooltip>
      );
    }

    return item;
  };

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="no-print w-[240px]">
        {actions.map((action) => {
          if (action.hidden) {
            return null;
          }

          if (action.dropdown) {
            return (
              <DropdownMenuSub key={action.label}>
                <DropdownMenuSubTrigger
                  data-testid={`notebook-menu-dropdown-${action.label}`}
                >
                  {renderLabel(action)}
                </DropdownMenuSubTrigger>
                <DropdownMenuPortal>
                  <DropdownMenuSubContent>
                    {action.dropdown.map((action) => {
                      return (
                        <React.Fragment key={action.label}>
                          {action.divider && <DropdownMenuSeparator />}
                          {renderLeafAction(action)}
                        </React.Fragment>
                      );
                    })}
                  </DropdownMenuSubContent>
                </DropdownMenuPortal>
              </DropdownMenuSub>
            );
          }

          return (
            <React.Fragment key={action.label}>
              {action.divider && <DropdownMenuSeparator />}
              {renderLeafAction(action)}
            </React.Fragment>
          );
        })}
        <DropdownMenuSeparator />
        <div className="flex-1 px-2 text-xs text-muted-foreground">
          <span>Version: {getMarimoVersion()}</span>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
