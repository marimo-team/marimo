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
import { renderMinimalShortcut } from "../shortcuts/renderShortcut";
import { useNotebookActions } from "./actions/useNotebookActions";
import { ActionButton } from "./actions/types";

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
        <span className="flex-1">{action.label}</span>
        {action.hotkey && renderMinimalShortcut(action.hotkey)}
        {action.rightElement}
      </>
    );
  };

  const renderLeafAction = (action: ActionButton) => {
    return (
      <DropdownMenuItem
        key={action.label}
        variant={action.variant}
        onSelect={(evt) => action.handle(evt)}
        data-testid={`notebook-menu-dropdown-${action.label}`}
      >
        {renderLabel(action)}
      </DropdownMenuItem>
    );
  };

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="no-print w-[220px]">
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
                    {action.dropdown.map(renderLeafAction)}
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
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
