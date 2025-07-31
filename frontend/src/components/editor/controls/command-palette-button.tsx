/* Copyright 2024 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { CommandIcon } from "lucide-react";
import React from "react";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { Button } from "../inputs/Inputs";
import { commandPaletteAtom } from "./command-palette";

export const CommandPaletteButton: React.FC = () => {
  const setCommandPaletteOpen = useSetAtom(commandPaletteAtom);
  const toggle = () => setCommandPaletteOpen((value) => !value);

  return (
    <Tooltip content={renderShortcut("global.commandPalette")}>
      <Button
        data-testid="command-palette-button"
        onClick={toggle}
        shape="rectangle"
        color="hint-green"
      >
        <CommandIcon strokeWidth={1.5} size={18} />
      </Button>
    </Tooltip>
  );
};
