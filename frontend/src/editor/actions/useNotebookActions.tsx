/* Copyright 2023 Marimo. All rights reserved. */
import { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { runDuringPresentMode } from "@/core/mode";
import { downloadHTMLAsImage } from "@/utils/download";
import { useSetAtom } from "jotai";
import { ImageIcon, CommandIcon, ZapIcon } from "lucide-react";
import { commandPalletteAtom } from "../CommandPallette";
import { useCellActions, useCells } from "@/core/state/cells";
import { saveCellConfig } from "@/core/network/requests";
import { Objects } from "@/utils/objects";
import { useRunCells } from "../cell/useRunCells";

interface Action {
  label: string;
  hotkey?: HotkeyAction;
  icon?: React.ReactNode;
  hidden?: boolean;
  handle: () => void;
}

export function useNotebookActions(opts: { filename?: string | null }) {
  const { filename } = opts;

  const cells = useCells()
  const {
    updateCellConfig
  } = useCellActions();
  const setCommandPalletteOpen = useSetAtom(commandPalletteAtom);
  const runCells = useRunCells();

  const disabledCells = cells.present.filter(cell => cell.config.disabled);

  const actions: Action[] = [
    {
      icon: <ImageIcon size={13} strokeWidth={1.5} />,
      label: "Export to PNG",
      handle: async () => {
        await runDuringPresentMode(() => {
          downloadHTMLAsImage(document.body, filename || "screenshot.png");
        });
      },
    },
    {
      icon: <ZapIcon size={13} strokeWidth={1.5} />,
      label: "Enable cells and run",
      hidden: disabledCells.length === 0,
      handle: async () => {
        const ids = disabledCells.map(cell => cell.key);
        const newConfigs = Objects.fromEntries(ids.map(cellId => [cellId, { disabled: null }]));
        // send to BE
        await saveCellConfig({ configs: newConfigs });
        // update on FE
        ids.forEach(cellId => updateCellConfig({ cellId, config: { disabled: true } }));
        // run all cells
        await runCells(disabledCells);
      },
    },
    {
      icon: <CommandIcon size={13} strokeWidth={1.5} />,
      label: "Command Palette",
      hotkey: "global.commandPalette",
      handle: () => setCommandPalletteOpen((open) => !open),
    },
  ];

  return actions.filter(a => !a.hidden);
}
