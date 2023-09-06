/* Copyright 2023 Marimo. All rights reserved. */
import { Button } from "@/editor/inputs/Inputs";
import { CommandIcon, ImageIcon, MenuIcon } from "lucide-react";
import React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { downloadHTMLAsImage } from "@/utils/download";
import { commandPalletteAtom } from "@/editor/CommandPallette";
import { useSetAtom } from "jotai";
import { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { renderMinimalShortcut } from "../shortcuts/renderShortcut";

interface Props {
  filename: string | null;
}

interface Action {
  label: string;
  hotkey?: HotkeyAction;
  icon?: React.ReactNode;
  handle: () => void;
}

export const MenuDropdown: React.FC<Props> = ({ filename }) => {
  const setCommandPalletteOpen = useSetAtom(commandPalletteAtom);

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

  const actions: Action[] = [
    {
      icon: <ImageIcon size={13} strokeWidth={1.5} />,
      label: "Export to PNG",
      handle: () =>
        downloadHTMLAsImage(document.body, filename || "screenshot.png"),
    },
    {
      icon: <CommandIcon size={13} strokeWidth={1.5} />,
      label: "Command Palette",
      hotkey: "global.commandPalette",
      handle: () => setCommandPalletteOpen((open) => !open),
    },
  ];

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
