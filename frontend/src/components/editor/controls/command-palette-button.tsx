/* Copyright 2024 Marimo. All rights reserved. */
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { CommandIcon } from "lucide-react";
import React from "react";
import { Button } from "../inputs/Inputs";
import { useSetAtom } from "jotai";
import { commandPaletteAtom } from "./command-palette";

export const CommandPaletteButton: React.FC = () => {
  const setCommandPaletteOpen = useSetAtom(commandPaletteAtom);
  const toggle = () => setCommandPaletteOpen((value) => !value);

  return (
    <Tooltip content={renderShortcut("global.commandPalette")}>
      <Button onClick={toggle} shape="rectangle" color="white">
        <CommandIcon strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};
