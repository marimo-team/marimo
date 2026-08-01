/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import type { RefObject } from "react";
import {
  BookMarkedIcon,
  CheckIcon,
  ChevronDownCircleIcon,
  ChevronRightCircleIcon,
  ClipboardCopyIcon,
  CodeIcon,
  CommandIcon,
  DatabaseIcon,
  DiamondPlusIcon,
  DownloadIcon,
  EditIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  FastForwardIcon,
  FileIcon,
  Files,
  FileTextIcon,
  FolderDownIcon,
  GlobeIcon,
  HardDrive,
  Home,
  ImageIcon,
  KeyboardIcon,
  LayoutTemplateIcon,
  LinkIcon,
  MessageCircleQuestionIcon,
  MessagesSquareIcon,
  NotebookIcon,
  PanelLeftIcon,
  PowerSquareIcon,
  PresentationIcon,
  SettingsIcon,
  Share2Icon,
  SparklesIcon,
  Undo2Icon,
  XCircleIcon,
  ZapIcon,
} from "lucide-react";
import {
  settingDialogAtom,
  useOpenSettingsToTab,
} from "@/components/app-config/state";
import { FeedbackModal } from "@/components/editor/chrome/components/feedback-button";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import { GitHubIcon } from "@/components/icons/github";
import { MarimoPlusIcon } from "@/components/icons/marimo-icons";
import { YouTubeIcon } from "@/components/icons/youtube";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { PairWithAgentModal } from "@/components/editor/actions/pair-with-agent-modal";
import { ShareStaticNotebookModal } from "@/components/static-html/share-modal";
import { toast } from "@/components/ui/use-toast";
import {
  canUndoDeletesAtom,
  getNotebook,
  hasDisabledCellsAtom,
  undoLabelAtom,
  useCellActions,
} from "@/core/cells/cells";
import { disabledCellIds } from "@/core/cells/utils";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { aiEnabledAtom, useResolvedMarimoConfig } from "@/core/config/config";
import { Constants } from "@/core/constants";
import { useLayoutActions, useLayoutState } from "@/core/layout/layout";
import { useTogglePresenting } from "@/core/layout/useTogglePresenting";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { useRequestClient } from "@/core/network/requests";
import { useFilename } from "@/core/saving/filename";
import { createShareableLink } from "@/core/wasm/share";
import { isWasm } from "@/core/wasm/utils";
import { copyToClipboard } from "@/utils/copy";
import { Objects } from "@/utils/objects";
import { Strings } from "@/utils/strings";
import { newNotebookURL } from "@/utils/urls";
import { useRunAllCells } from "../cell/useRunCells";
import { useChromeActions, useChromeState } from "../chrome/state";
import { isPanelHidden, PANELS } from "../chrome/types";
import { AddConnectionDialogContent } from "../connections/add-connection-dialog";
import { keyboardShortcutsAtom } from "../controls/keyboard-shortcuts";
import { commandPaletteAtom } from "../controls/state";
import { displayLayoutName, getLayoutIcon } from "../renderers/layout-select";
import { LAYOUT_TYPES } from "../renderers/types";
import { ExportDialog } from "./export-dialog/export-dialog";
import {
  applyExportOptionOverrides,
  exportOptionsAtom,
  type ExportFormat,
  type ExportOptionOverrides,
} from "./export-dialog/state";
import type { ActionButton } from "./types";
import { useCopyNotebook } from "./useCopyNotebook";
import { useRestartKernel } from "./useRestartKernel";
import { useSetCodeVisibility } from "./useSetCodeVisibility";

const NOOP_HANDLER = (event?: Event) => {
  event?.preventDefault();
  event?.stopPropagation();
};

export function useNotebookActions({
  exportDialogReturnFocusRef,
}: {
  exportDialogReturnFocusRef?: RefObject<HTMLElement | null>;
} = {}) {
  const filename = useFilename();
  const { openModal, closeModal } = useImperativeModal();
  const { toggleApplication } = useChromeActions();
  const { selectedPanel } = useChromeState();
  const [viewState] = useAtom(viewStateAtom);
  const kioskMode = useAtomValue(kioskModeAtom);
  const setCodeVisibility = useSetCodeVisibility();
  const [resolvedConfig] = useResolvedMarimoConfig();
  const capabilities = useAtomValue(capabilitiesAtom);
  const aiEnabled = useAtomValue(aiEnabledAtom);

  const {
    updateCellConfig,
    undoDeleteCell,
    clearAllCellOutputs,
    addSetupCellIfDoesntExist,
    collapseAllCells,
    expandAllCells,
  } = useCellActions();
  const restartKernel = useRestartKernel();
  const runAllCells = useRunAllCells();
  const copyNotebook = useCopyNotebook(filename);
  const setCommandPaletteOpen = useSetAtom(commandPaletteAtom);
  const setSettingsDialogOpen = useSetAtom(settingDialogAtom);
  const { handleClick: openSettings } = useOpenSettingsToTab();
  const setKeyboardShortcutsOpen = useSetAtom(keyboardShortcutsAtom);
  const setExportOptions = useSetAtom(exportOptionsAtom);
  const { readCode, saveCellConfig } = useRequestClient();

  const hasDisabledCells = useAtomValue(hasDisabledCellsAtom);
  const canUndoDeletes = useAtomValue(canUndoDeletesAtom);
  const undoLabel = useAtomValue(undoLabelAtom);
  const { selectedLayout } = useLayoutState();
  const { setLayoutView } = useLayoutActions();
  const togglePresenting = useTogglePresenting();
  // Fallback: if sharing is undefined, all options are enabled by default
  const sharingHtmlEnabled = resolvedConfig.sharing?.html ?? true;
  const sharingWasmEnabled = resolvedConfig.sharing?.wasm ?? true;
  const sharingMolabEnabled = resolvedConfig.sharing?.molab ?? true;
  const isSlidesLayout = selectedLayout === "slides";

  const renderCheckboxElement = (checked: boolean) => (
    <div className="w-8 flex justify-end">
      {checked && <CheckIcon size={14} />}
    </div>
  );

  const openExportDialog = (
    initialFormat?: ExportFormat,
    optionOverrides?: ExportOptionOverrides,
  ) => {
    if (optionOverrides) {
      setExportOptions((current) =>
        applyExportOptionOverrides(current, optionOverrides),
      );
    }
    openModal(
      <ExportDialog
        initialFormat={initialFormat}
        onClose={closeModal}
        returnFocusRef={exportDialogReturnFocusRef}
      />,
    );
  };

  const actions: ActionButton[] = [
    {
      icon: <DownloadIcon size={14} strokeWidth={1.5} />,
      label: "Export…",
      additionalKeywords: [
        "download",
        "html",
        "markdown",
        "ipynb",
        "pdf",
        "script",
        "png",
      ],
      handle: () => openExportDialog(),
    },
    {
      icon: <DownloadIcon size={14} strokeWidth={1.5} />,
      label: "Download",
      handle: NOOP_HANDLER,
      dropdown: [
        {
          icon: <FolderDownIcon size={14} strokeWidth={1.5} />,
          label: "Download as HTML",
          handle: () =>
            openExportDialog("html", { html: { includeCode: true } }),
        },
        {
          icon: <FolderDownIcon size={14} strokeWidth={1.5} />,
          label: "Download as HTML (exclude code)",
          handle: () =>
            openExportDialog("html", { html: { includeCode: false } }),
        },
        {
          icon: (
            <MarkdownIcon strokeWidth={1.5} style={{ width: 14, height: 14 }} />
          ),
          label: "Download as Markdown",
          handle: () => openExportDialog("markdown"),
        },
        {
          icon: <NotebookIcon size={14} strokeWidth={1.5} />,
          label: "Download as ipynb",
          handle: () => openExportDialog("ipynb"),
        },
        {
          icon: <CodeIcon size={14} strokeWidth={1.5} />,
          label: "Download notebook source",
          handle: () =>
            openExportDialog("script", { script: { type: "source" } }),
        },
        {
          icon: <CodeIcon size={14} strokeWidth={1.5} />,
          label: "Download flat script",
          handle: () =>
            openExportDialog("script", { script: { type: "flat" } }),
        },
        {
          divider: true,
          icon: <ImageIcon size={14} strokeWidth={1.5} />,
          label: "Download as PNG",
          handle: () => openExportDialog("png"),
        },
        isSlidesLayout
          ? {
              divider: true,
              icon: <FileIcon size={14} strokeWidth={1.5} />,
              label: "Download as PDF",
              handle: NOOP_HANDLER,
              dropdown: [
                {
                  icon: <FileIcon size={14} strokeWidth={1.5} />,
                  label: "Document Layout",
                  handle: () =>
                    openExportDialog("pdf", {
                      pdf: { preset: "document" },
                    }),
                },
                {
                  icon: <FileIcon size={14} strokeWidth={1.5} />,
                  label: "Slides Layout",
                  rightElement: (
                    <span className="ml-3 shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                      Recommended
                    </span>
                  ),
                  handle: () =>
                    openExportDialog("pdf", {
                      pdf: { preset: "slides" },
                    }),
                },
              ],
            }
          : {
              divider: true,
              icon: <FileIcon size={14} strokeWidth={1.5} />,
              label: "Download as PDF",
              handle: () =>
                openExportDialog("pdf", {
                  pdf: { preset: "document" },
                }),
            },
      ],
    },

    {
      icon: <SparklesIcon size={14} strokeWidth={1.5} />,
      label: "Pair with an agent",
      hidden: isWasm(),
      handle: async () => {
        openModal(<PairWithAgentModal onClose={closeModal} />);
      },
    },

    {
      icon: <Share2Icon size={14} strokeWidth={1.5} />,
      label: "Share",
      handle: NOOP_HANDLER,
      hidden:
        !sharingHtmlEnabled && !sharingWasmEnabled && !sharingMolabEnabled,
      dropdown: [
        {
          icon: <GlobeIcon size={14} strokeWidth={1.5} />,
          label: "Publish HTML to web",
          hidden: !sharingHtmlEnabled,
          handle: async () => {
            openModal(<ShareStaticNotebookModal onClose={closeModal} />);
          },
        },
        {
          icon: <LinkIcon size={14} strokeWidth={1.5} />,
          label: "Create WebAssembly link",
          hidden: !sharingWasmEnabled,
          handle: async () => {
            const code = await readCode();
            const url = createShareableLink({ code: code.contents });
            await copyToClipboard(url);
            toast({
              title: "Copied",
              description: "Link copied to clipboard.",
            });
          },
        },
        {
          icon: <MarimoPlusIcon size={14} strokeWidth={1.5} />,
          label: "Create molab notebook",
          hidden: !sharingMolabEnabled,
          handle: async () => {
            const code = await readCode();
            const url = createShareableLink({
              code: code.contents,
              baseUrl: `${Constants.molab}/new`,
            });
            window.open(url, "_blank");
          },
        },
      ],
    },

    {
      icon: <PanelLeftIcon size={14} strokeWidth={1.5} />,
      label: "Helper panel",
      redundant: true,
      handle: NOOP_HANDLER,
      dropdown: PANELS.flatMap((panel) => {
        // Still show the AI panel in the command palette so users can try AI
        // features. When AI is disabled, open settings instead of the panel.
        const openAiSettingsWhenDisabled = panel.type === "ai" && !aiEnabled;
        if (
          isPanelHidden({ panel, capabilities, aiEnabled }) &&
          !openAiSettingsWhenDisabled
        ) {
          return [];
        }
        const { type: id, Icon, additionalKeywords } = panel;
        return {
          label: Strings.startCase(id),
          rightElement: renderCheckboxElement(selectedPanel === id),
          icon: <Icon size={14} strokeWidth={1.5} />,
          handle: () => {
            if (openAiSettingsWhenDisabled) {
              openSettings("ai", "ai-features");
              return;
            }
            toggleApplication(id);
          },
          additionalKeywords,
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
      icon: <Files size={14} strokeWidth={1.5} />,
      label: "Duplicate notebook",
      hidden: !filename || isWasm(),
      handle: copyNotebook,
    },
    {
      icon: <ClipboardCopyIcon size={14} strokeWidth={1.5} />,
      label: "Copy code to clipboard",
      hidden: !filename,
      handle: async () => {
        const code = await readCode();
        await copyToClipboard(code.contents);
        toast({
          title: "Copied",
          description: "Code copied to clipboard.",
        });
      },
    },
    {
      icon: <ZapIcon size={14} strokeWidth={1.5} />,
      label: "Enable all cells",
      hidden: !hasDisabledCells || kioskMode,
      handle: async () => {
        const notebook = getNotebook();
        const ids = disabledCellIds(notebook);
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
      divider: true,
      icon: <DiamondPlusIcon size={14} strokeWidth={1.5} />,
      label: "Add setup cell",
      handle: () => {
        addSetupCellIfDoesntExist({});
      },
    },
    {
      icon: <DatabaseIcon size={14} strokeWidth={1.5} />,
      label: "Add database connection",
      handle: () => {
        openModal(<AddConnectionDialogContent onClose={closeModal} />);
      },
    },
    {
      icon: <HardDrive size={14} strokeWidth={1.5} />,
      label: "Add remote storage",
      handle: () => {
        openModal(
          <AddConnectionDialogContent
            defaultTab="storage"
            onClose={closeModal}
          />,
        );
      },
    },
    {
      icon: <Undo2Icon size={14} strokeWidth={1.5} />,
      label: undoLabel,
      hidden: !canUndoDeletes || kioskMode,
      handle: () => {
        undoDeleteCell();
      },
    },
    {
      icon: <PowerSquareIcon size={14} strokeWidth={1.5} />,
      label: "Restart kernel",
      variant: "danger",
      handle: restartKernel,
      additionalKeywords: ["reset", "reload", "restart"],
    },
    {
      icon: <FastForwardIcon size={14} strokeWidth={1.5} />,
      label: "Re-run all cells",
      redundant: true,
      hotkey: "global.runAll",
      handle: async () => {
        runAllCells();
      },
    },
    {
      icon: <XCircleIcon size={14} strokeWidth={1.5} />,
      label: "Clear all outputs",
      redundant: true,
      handle: () => {
        clearAllCellOutputs();
      },
    },
    {
      icon: <EyeIcon size={14} strokeWidth={1.5} />,
      label: "Show all code",
      hotkey: "global.showAllCode",
      handle: () => setCodeVisibility(false, "code"),
      redundant: true,
    },
    {
      icon: <EyeOffIcon size={14} strokeWidth={1.5} />,
      label: "Hide all code",
      hotkey: "global.hideAllCode",
      handle: () => setCodeVisibility(true, "code"),
      redundant: true,
    },
    {
      icon: <EyeIcon size={14} strokeWidth={1.5} />,
      label: "Show all markdown code",
      hotkey: "global.showAllMarkdownCode",
      handle: () => setCodeVisibility(false, "markdown"),
      redundant: true,
    },
    {
      icon: <EyeOffIcon size={14} strokeWidth={1.5} />,
      label: "Hide all markdown code",
      hotkey: "global.hideAllMarkdownCode",
      handle: () => setCodeVisibility(true, "markdown"),
      redundant: true,
    },
    {
      icon: <ChevronRightCircleIcon size={14} strokeWidth={1.5} />,
      label: "Collapse all sections",
      hotkey: "global.collapseAllSections",
      handle: collapseAllCells,
      redundant: true,
    },
    {
      icon: <ChevronDownCircleIcon size={14} strokeWidth={1.5} />,
      label: "Expand all sections",
      hotkey: "global.expandAllSections",
      handle: expandAllCells,
      redundant: true,
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
      icon: <SettingsIcon size={14} strokeWidth={1.5} />,
      label: "User settings",
      handle: () => setSettingsDialogOpen((open) => !open),
      redundant: true,
      additionalKeywords: ["preferences", "options", "configuration"],
    },
    {
      icon: <MessageCircleQuestionIcon size={14} strokeWidth={1.5} />,
      label: "Report an issue",
      additionalKeywords: ["feedback", "bug", "issue", "report", "diagnostics"],
      handle: () => openModal(<FeedbackModal onClose={closeModal} />),
    },
    {
      icon: <ExternalLinkIcon size={14} strokeWidth={1.5} />,
      label: "Resources",
      handle: NOOP_HANDLER,
      dropdown: [
        {
          icon: <BookMarkedIcon size={14} strokeWidth={1.5} />,
          label: "Documentation",
          handle: () => {
            window.open(Constants.docsPage, "_blank");
          },
        },
        {
          icon: <GitHubIcon className="h-3.5 w-3.5" />,
          label: "GitHub",
          handle: () => {
            window.open(Constants.githubPage, "_blank");
          },
        },
        {
          icon: <MessagesSquareIcon size={14} strokeWidth={1.5} />,
          label: "Discord Community",
          handle: () => {
            window.open(Constants.discordLink, "_blank");
          },
        },
        {
          icon: <YouTubeIcon className="h-3.5 w-3.5" />,
          label: "YouTube",
          handle: () => {
            window.open(Constants.youtube, "_blank");
          },
        },
        {
          icon: <FileTextIcon size={14} strokeWidth={1.5} />,
          label: "Changelog",
          handle: () => {
            window.open(Constants.releasesPage, "_blank");
          },
        },
      ],
    },

    {
      divider: true,
      icon: <Home size={14} strokeWidth={1.5} />,
      label: "Open home",
      // If file is in the url, then we ran `marimo edit`
      // without a specific file
      hidden: !location.search.includes("file"),
      handle: () => {
        const withoutSearch = document.baseURI.split("?")[0];
        window.open(withoutSearch, "_blank", "noopener");
      },
    },

    {
      icon: <MarimoPlusIcon size={14} strokeWidth={1.5} />,
      label: "New notebook",
      // If file is in the url, then we ran `marimo edit`
      // without a specific file
      hidden: !location.search.includes("file"),
      handle: () => {
        const url = newNotebookURL();
        window.open(url, "_blank");
      },
    },
  ];

  return actions
    .filter((a) => !a.hidden)
    .map((action) => {
      if (action.dropdown) {
        return {
          ...action,
          dropdown: action.dropdown.filter((item) => !item.hidden),
        };
      }
      return action;
    });
}
