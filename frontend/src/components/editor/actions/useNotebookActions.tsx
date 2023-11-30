/* Copyright 2023 Marimo. All rights reserved. */
import { runDuringPresentMode } from "@/core/mode";
import { downloadHTMLAsImage } from "@/utils/download";
import { useSetAtom } from "jotai";
import {
  ImageIcon,
  CommandIcon,
  ZapIcon,
  ZapOffIcon,
  BookMarkedIcon,
  FolderDownIcon,
  ClipboardCopyIcon,
} from "lucide-react";
import { commandPalletteAtom } from "../CommandPallette";
import {
  disabledCellIds,
  enabledCellIds,
  useCellActions,
  useNotebook,
} from "@/core/cells/cells";
import { readCode, saveCellConfig } from "@/core/network/requests";
import { Objects } from "@/utils/objects";
import { ActionButton } from "./types";
import { downloadAsHTML } from "@/core/static/download-html";
import { toast } from "@/components/ui/use-toast";
import { useFilename } from "@/core/saving/filename";

export function useNotebookActions() {
  const [filename] = useFilename();

  const notebook = useNotebook();
  const { updateCellConfig } = useCellActions();
  const setCommandPalletteOpen = useSetAtom(commandPalletteAtom);

  const disabledCells = disabledCellIds(notebook);
  const enabledCells = enabledCellIds(notebook);

  const actions: ActionButton[] = [
    {
      icon: <ImageIcon size={14} strokeWidth={1.5} />,
      label: "Export as PNG",
      handle: async () => {
        await runDuringPresentMode(() => {
          const app = document.getElementById("App");
          if (!app) {
            return;
          }
          downloadHTMLAsImage(app, filename || "screenshot.png");
        });
      },
    },
    {
      icon: <FolderDownIcon size={14} strokeWidth={1.5} />,
      label: "Export as HTML",
      handle: async () => {
        if (!filename) {
          toast({
            variant: "danger",
            title: "Error",
            description: "Notebooks must be named to be exported.",
          });
          return;
        }
        await downloadAsHTML({ filename });
      },
    },
    {
      icon: <ZapIcon size={14} strokeWidth={1.5} />,
      label: "Enable all cells",
      hidden: disabledCells.length === 0,
      handle: async () => {
        const ids = disabledCells.map((cell) => cell.id);
        const newConfigs = Objects.fromEntries(
          ids.map((cellId) => [cellId, { disabled: false }])
        );
        // send to BE
        await saveCellConfig({ configs: newConfigs });
        // update on FE
        ids.forEach((cellId) =>
          updateCellConfig({ cellId, config: { disabled: false } })
        );
      },
    },
    {
      icon: <ZapOffIcon size={14} strokeWidth={1.5} />,
      label: "Disable all cells",
      hidden: enabledCells.length === 0,
      handle: async () => {
        const ids = enabledCells.map((cell) => cell.id);
        const newConfigs = Objects.fromEntries(
          ids.map((cellId) => [cellId, { disabled: true }])
        );
        // send to BE
        await saveCellConfig({ configs: newConfigs });
        // update on FE
        ids.forEach((cellId) =>
          updateCellConfig({ cellId, config: { disabled: true } })
        );
      },
    },

    {
      icon: <ClipboardCopyIcon size={14} strokeWidth={1.5} />,
      label: "Copy code to clipboard",
      hidden: !filename,
      handle: async () => {
        const code = await readCode();
        navigator.clipboard.writeText(code.contents);
        toast({
          title: "Copied",
          description: "Code copied to clipboard.",
        });
      },
    },

    {
      icon: <CommandIcon size={14} strokeWidth={1.5} />,
      label: "Command palette",
      hotkey: "global.commandPalette",
      handle: () => setCommandPalletteOpen((open) => !open),
    },

    {
      icon: <BookMarkedIcon size={14} strokeWidth={1.5} />,
      label: "Open documentation",
      handle: () => {
        window.open("https://docs.marimo.io", "_blank");
      },
    },
  ];

  return actions.filter((a) => !a.hidden);
}
