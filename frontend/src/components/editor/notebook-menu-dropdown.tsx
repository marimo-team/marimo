/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/editor/inputs/Inputs";
import { MenuIcon } from "lucide-react";
import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { renderMinimalShortcut } from "../shortcuts/renderShortcut";
import { useNotebookActions } from "./actions/useNotebookActions";

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

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="no-print w-[220px]">
        {actions.map((action) => (
          <DropdownMenuItem
            key={action.label}
            variant={action.variant}
            onSelect={(evt) => action.handle(evt)}
            data-testid={`notebook-menu-dropdown-${action.label}`}
          >
            {action.icon && <span className="flex-0 mr-2">{action.icon}</span>}
            <span className="flex-1">{action.label}</span>
            {action.hotkey && renderMinimalShortcut(action.hotkey)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
