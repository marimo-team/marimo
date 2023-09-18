/* Copyright 2023 Marimo. All rights reserved. */
import { Button } from "@/editor/inputs/Inputs";
import { MenuIcon } from "lucide-react";
import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { renderMinimalShortcut } from "../components/shortcuts/renderShortcut";
import { useNotebookActions } from "./actions/useNotebookActions";

interface Props {
  filename: string | null;
}

export const NotebookMenuDropdown: React.FC<Props> = ({ filename }) => {
  const actions = useNotebookActions({ filename });

  const button = (
    <Button
      aria-label="Config"
      shape="circle"
      size="small"
      className="h-[27px] w-[27px]"
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
          <DropdownMenuItem key={action.label} onSelect={() => action.handle()}>
            {action.icon && <span className="flex-0 mr-2">{action.icon}</span>}
            <span className="flex-1">{action.label}</span>
            {action.hotkey && renderMinimalShortcut(action.hotkey)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
