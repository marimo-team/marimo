/* Copyright 2024 Marimo. All rights reserved. */
import {
  kioskModeAtom,
  runDuringPresentMode,
  viewStateAtom,
} from "@/core/mode";
import { downloadBlob, downloadHTMLAsImage } from "@/utils/download";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  ImageIcon,
  CommandIcon,
  ZapIcon,
  ZapOffIcon,
  BookMarkedIcon,
  FolderDownIcon,
  ClipboardCopyIcon,
  Share2Icon,
  PowerSquareIcon,
  GlobeIcon,
  LinkIcon,
  DownloadIcon,
  CodeIcon,
  PanelLeftIcon,
  CheckIcon,
  KeyboardIcon,
  Undo2Icon,
  FileIcon,
  Home,
  PresentationIcon,
  EditIcon,
  LayoutTemplateIcon,
} from "lucide-react";
import { commandPaletteAtom } from "../controls/command-palette";
import { useCellActions, useNotebook } from "@/core/cells/cells";
import {
  canUndoDeletes,
  disabledCellIds,
  enabledCellIds,
} from "@/core/cells/utils";
import {
  exportAsMarkdown,
  readCode,
  saveCellConfig,
} from "@/core/network/requests";
import { Objects } from "@/utils/objects";
import type { ActionButton } from "./types";
import { downloadAsHTML } from "@/core/static/download-html";
import { toast } from "@/components/ui/use-toast";
import { useFilename } from "@/core/saving/filename";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { ShareStaticNotebookModal } from "@/components/static-html/share-modal";
import { useRestartKernel } from "./useRestartKernel";
import { createShareableLink } from "@/core/wasm/share";
import { useChromeActions, useChromeState } from "../chrome/state";
import { PANELS } from "../chrome/types";
import { startCase } from "lodash-es";
import { keyboardShortcutsAtom } from "../controls/keyboard-shortcuts";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import { Filenames } from "@/utils/filenames";
import { LAYOUT_TYPES } from "../renderers/types";
import { displayLayoutName, getLayoutIcon } from "../renderers/layout-select";
import { useLayoutState, useLayoutActions } from "@/core/layout/layout";
import { useTogglePresenting } from "@/core/layout/useTogglePresenting";

const NOOP_HANDLER = (event?: Event) => {
  event?.preventDefault();
  event?.stopPropagation();
};

export function useNotebookActions() {
  const [filename] = useFilename();
  const { openModal, closeModal } = useImperativeModal();
  const { openApplication } = useChromeActions();
  const { selectedPanel } = useChromeState();
  const [viewState] = useAtom(viewStateAtom);
  const kioskMode = useAtomValue(kioskModeAtom);

  const notebook = useNotebook();
  const { updateCellConfig, undoDeleteCell } = useCellActions();
  const restartKernel = useRestartKernel();
  const setCommandPaletteOpen = useSetAtom(commandPaletteAtom);
  const setKeyboardShortcutsOpen = useSetAtom(keyboardShortcutsAtom);

  const disabledCells = disabledCellIds(notebook);
  const enabledCells = enabledCellIds(notebook);
  const { selectedLayout } = useLayoutState();
  const { setLayoutView } = useLayoutActions();
  const togglePresenting = useTogglePresenting();

  const actions: ActionButton[] = [
    {
      icon: <Share2Icon size={14} strokeWidth={1.5} />,
      label: "Share",
      handle: NOOP_HANDLER,
      dropdown: [
        {
          icon: <GlobeIcon size={14} strokeWidth={1.5} />,
          label: "Publish HTML to web",
          handle: async () => {
            openModal(<ShareStaticNotebookModal onClose={closeModal} />);
          },
        },
        {
          icon: <LinkIcon size={14} strokeWidth={1.5} />,
          label: "Create WebAssembly link",
          handle: async () => {
            const code = await readCode();
            const url = createShareableLink({ code: code.contents });
            window.navigator.clipboard.writeText(url);
            toast({
              title: "Copied",
              description: "Link copied to clipboard.",
            });
          },
        },
      ],
    },
    {
      icon: <DownloadIcon size={14} strokeWidth={1.5} />,
      label: "Download",
      handle: NOOP_HANDLER,
      dropdown: [
        {
          icon: <FolderDownIcon size={14} strokeWidth={1.5} />,
          label: "Download as HTML",
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
          icon: <ImageIcon size={14} strokeWidth={1.5} />,
          label: "Download as PNG",
          handle: async () => {
            const toasted = toast({
              title: "Starting download",
              description: "Downloading as PNG...",
            });

            await runDuringPresentMode(async () => {
              const app = document.getElementById("App");
              if (!app) {
                return;
              }

              // Wait 3 seconds for the app to render
              await new Promise((resolve) => setTimeout(resolve, 3000));

              await downloadHTMLAsImage(app, document.title);
            });

            toasted.dismiss();
          },
        },
        {
          icon: <FileIcon size={14} strokeWidth={1.5} />,
          label: "Print PDF",
          handle: async () => {
            const toasted = toast({
              title: "Starting download",
              description: "Downloading as PDF...",
            });

            await runDuringPresentMode(async () => {
              // Wait 3 seconds for the app to render
              await new Promise((resolve) => setTimeout(resolve, 3000));
              toasted.dismiss();

              const beforeprint = new Event("export-beforeprint");
              const afterprint = new Event("export-afterprint");
              function print() {
                window.dispatchEvent(beforeprint);
                setTimeout(() => window.print(), 0);
                setTimeout(() => window.dispatchEvent(afterprint), 0);
              }
              print();
            });
          },
        },
        {
          icon: (
            <MarkdownIcon strokeWidth={1.5} style={{ width: 14, height: 14 }} />
          ),
          label: "Download as Markdown",
          handle: async () => {
            const md = await exportAsMarkdown({ download: false });
            downloadBlob(
              new Blob([md], { type: "text/plain" }),
              Filenames.toMarkdown(document.title),
            );
          },
        },
        {
          icon: <CodeIcon size={14} strokeWidth={1.5} />,
          label: "Download Python code",
          handle: async () => {
            const code = await readCode();
            downloadBlob(
              new Blob([code.contents], { type: "text/plain" }),
              Filenames.toPY(document.title),
            );
          },
        },
      ],
    },

    {
      divider: true,
      icon: <PanelLeftIcon size={14} strokeWidth={1.5} />,
      label: "Helper panel",
      handle: NOOP_HANDLER,
      dropdown: PANELS.flatMap(({ type, Icon, hidden }) => {
        if (hidden) {
          return [];
        }
        return {
          label: startCase(type),
          rightElement: (
            <div className="w-8 flex justify-end">
              {selectedPanel === type && <CheckIcon size={14} />}
            </div>
          ),
          icon: <Icon size={14} strokeWidth={1.5} />,
          handle: () => openApplication(type),
        };
      }),
    },

    {
      icon: <PresentationIcon size={14} strokeWidth={1.5} />,
      label: "Present as",
      handle: NOOP_HANDLER,
      dropdown: [
        {
          icon:
            viewState.mode === "present" ? (
              <EditIcon size={14} strokeWidth={1.5} />
            ) : (
              <LayoutTemplateIcon size={14} strokeWidth={1.5} />
            ),
          label: "Toggle app view",
          hotkey: "global.hideCode",
          handle: () => {
            togglePresenting();
          },
        },
        ...LAYOUT_TYPES.map((type, idx) => {
          const Icon = getLayoutIcon(type);
          return {
            divider: idx === 0,
            label: displayLayoutName(type),
            icon: <Icon size={14} strokeWidth={1.5} />,
            rightElement: (
              <div className="w-8 flex justify-end">
                {selectedLayout === type && <CheckIcon size={14} />}
              </div>
            ),
            handle: () => {
              setLayoutView(type);
              // Toggle if it's not in present mode
              if (viewState.mode === "edit") {
                togglePresenting();
              }
            },
          };
        }),
      ],
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
      icon: <ZapIcon size={14} strokeWidth={1.5} />,
      label: "Enable all cells",
      hidden: disabledCells.length === 0 || kioskMode,
      handle: async () => {
        const ids = disabledCells.map((cell) => cell.id);
        const newConfigs = Objects.fromEntries(
          ids.map((cellId) => [cellId, { disabled: false }]),
        );
        // send to BE
        await saveCellConfig({ configs: newConfigs });
        // update on FE
        for (const cellId of ids) {
          updateCellConfig({ cellId, config: { disabled: false } });
        }
      },
    },
    {
      icon: <ZapOffIcon size={14} strokeWidth={1.5} />,
      label: "Disable all cells",
      hidden: enabledCells.length === 0 || kioskMode,
      handle: async () => {
        const ids = enabledCells.map((cell) => cell.id);
        const newConfigs = Objects.fromEntries(
          ids.map((cellId) => [cellId, { disabled: true }]),
        );
        // send to BE
        await saveCellConfig({ configs: newConfigs });
        // update on FE
        for (const cellId of ids) {
          updateCellConfig({ cellId, config: { disabled: true } });
        }
      },
    },
    {
      icon: <Undo2Icon size={14} strokeWidth={1.5} />,
      label: "Undo cell deletion",
      hidden: !canUndoDeletes(notebook) || kioskMode,
      handle: () => {
        undoDeleteCell();
      },
    },

    {
      divider: true,
      icon: <CommandIcon size={14} strokeWidth={1.5} />,
      label: "Command palette",
      hotkey: "global.commandPalette",
      handle: () => setCommandPaletteOpen((open) => !open),
    },

    {
      icon: <KeyboardIcon size={14} strokeWidth={1.5} />,
      label: "Keyboard shortcuts",
      hotkey: "global.showHelp",
      handle: () => setKeyboardShortcutsOpen((open) => !open),
    },

    {
      icon: <BookMarkedIcon size={14} strokeWidth={1.5} />,
      label: "Open documentation",
      handle: () => {
        window.open("https://docs.marimo.io", "_blank");
      },
    },

    {
      divider: true,
      icon: <Home size={14} strokeWidth={1.5} />,
      label: "Return home",
      hidden: !location.search.includes("file"),
      handle: () => {
        window.location.href = document.baseURI;
      },
    },

    {
      icon: <PowerSquareIcon size={14} strokeWidth={1.5} />,
      label: "Restart kernel",
      variant: "danger",
      handle: restartKernel,
    },
  ];

  return actions.filter((a) => !a.hidden);
}
