/* Copyright 2024 Marimo. All rights reserved. */
import { downloadCellOutput } from "@/components/export/export-output-button";
import { Switch } from "@/components/ui/switch";
import { formatEditorViews } from "@/core/codemirror/format";
import {
  canToggleToLanguage,
  getCurrentLanguageAdapter,
  toggleToLanguage,
} from "@/core/codemirror/language/commands";
import {
  hasOnlyOneCellAtom,
  useCellActions,
  useCellIds,
} from "@/core/cells/cells";
import {
  ImageIcon,
  Code2Icon,
  ZapIcon,
  PlusCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronsUpIcon,
  ChevronsDownIcon,
  Trash2Icon,
  ZapOffIcon,
  PlayIcon,
  TextCursorInputIcon,
  EyeIcon,
  EyeOffIcon,
  SparklesIcon,
  DatabaseIcon,
} from "lucide-react";
import type { ActionButton } from "./types";
import { MultiIcon } from "@/components/icons/multi-icon";
import type { CellData } from "@/core/cells/types";
import type { CellId } from "@/core/cells/ids";
import { saveCellConfig } from "@/core/network/requests";
import type { EditorView } from "@codemirror/view";
import { useRunCell } from "../cell/useRunCells";
import { NameCellInput } from "./name-cell-input";
import { useAtomValue, useSetAtom } from "jotai";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DialogContent,
  DialogTitle,
  DialogHeader,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { MarkdownIcon, PythonIcon } from "../cell/code/icons";
import { aiEnabledAtom, autoInstantiateAtom } from "@/core/config/config";
import { useDeleteCellCallback } from "../cell/useDeleteCell";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import type { CellConfig, CellStatus } from "@/core/network/types";
import { kioskModeAtom } from "@/core/mode";

export interface CellActionButtonProps
  extends Pick<CellData, "name" | "config"> {
  cellId: CellId;
  status: CellStatus;
  hasOutput: boolean;
  getEditorView: () => EditorView | null;
}

interface Props {
  cell: CellActionButtonProps | null;
}

export function useCellActionButtons({ cell }: Props) {
  const {
    createNewCell: createCell,
    updateCellConfig,
    updateCellCode,
    updateCellName,
    moveCell,
    sendToTop,
    sendToBottom,
  } = useCellActions();
  const runCell = useRunCell(cell?.cellId);
  const hasOnlyOneCell = useAtomValue(hasOnlyOneCellAtom);
  const canDelete = !hasOnlyOneCell;
  const deleteCell = useDeleteCellCallback();
  const { openModal } = useImperativeModal();
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const autoInstantiate = useAtomValue(autoInstantiateAtom);
  const cellIds = useCellIds();
  const kioskMode = useAtomValue(kioskModeAtom);

  if (!cell || kioskMode) {
    return [];
  }

  const { cellId, config, getEditorView, name, hasOutput, status } = cell;
  const cellIdx = cellIds.inOrderIds.indexOf(cellId);
  const editorView = getEditorView();

  const toggleDisabled = async () => {
    const newConfig = { disabled: !config.disabled };
    await saveCellConfig({ configs: { [cellId]: newConfig } });
    updateCellConfig({ cellId, config: newConfig });
  };

  const toggleHideCode = async () => {
    const newConfig: Partial<CellConfig> = { hide_code: !config.hide_code };
    await saveCellConfig({ configs: { [cellId]: newConfig } });
    updateCellConfig({ cellId, config: newConfig });

    // If we're hiding the code, we should blur the editor
    // otherwise, we should focus it
    if (editorView) {
      if (newConfig.hide_code) {
        editorView.contentDOM.blur();
      } else {
        editorView.focus();
      }
    }
  };

  // Actions
  const actions: ActionButton[][] = [
    [
      {
        icon: <TextCursorInputIcon size={13} strokeWidth={1.5} />,
        label: "Name",
        disableClick: true,
        handle: (evt) => {
          evt?.stopPropagation();
          evt?.preventDefault();
        },
        handleHeadless: () => {
          openModal(
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Rename cell</DialogTitle>
              </DialogHeader>
              <div className="flex items-center justify-between">
                <Label htmlFor="cell-name">Cell name</Label>
                <NameCellInput
                  placeholder={`cell_${cellIdx}`}
                  value={name}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      e.stopPropagation();
                      openModal(null);
                    }
                  }}
                  onChange={(newName) =>
                    updateCellName({ cellId, name: newName })
                  }
                />
              </div>
            </DialogContent>,
          );
        },
        rightElement: (
          <NameCellInput
            placeholder={`cell_${cellIdx}`}
            value={name}
            onChange={(newName) => updateCellName({ cellId, name: newName })}
          />
        ),
      },
      {
        icon: <PlayIcon size={13} strokeWidth={1.5} />,
        label: "Run cell",
        hotkey: "cell.run",
        hidden:
          status === "running" ||
          status === "queued" ||
          status === "disabled-transitively" ||
          config.disabled,
        handle: () => runCell(),
      },
      {
        icon: <SparklesIcon size={13} strokeWidth={1.5} />,
        label: "AI completion",
        hidden: !aiEnabled,
        handle: () => {
          setAiCompletionCell((current) =>
            current === cellId ? null : cellId,
          );
        },
        hotkey: "cell.aiCompletion",
      },
      {
        icon: <ImageIcon size={13} strokeWidth={1.5} />,
        label: "Export output as PNG",
        hidden: !hasOutput,
        handle: () => downloadCellOutput(cellId),
      },
      {
        icon: <Code2Icon size={13} strokeWidth={1.5} />,
        label: "Format cell",
        hotkey: "cell.format",
        handle: () => {
          if (!editorView) {
            return;
          }
          formatEditorViews({ [cellId]: editorView }, updateCellCode);
        },
      },
      {
        icon: <MarkdownIcon />,
        label: "View as Markdown",
        hotkey: "cell.viewAsMarkdown",
        hidden: !canToggleToLanguage(editorView, "markdown"),
        handle: () => {
          if (!editorView) {
            return;
          }
          maybeAddMarimoImport(autoInstantiate, createCell);

          toggleToLanguage(editorView, "markdown");
        },
      },
      {
        icon: <DatabaseIcon size={13} strokeWidth={1.5} />,
        label: "View as SQL",
        hidden: !canToggleToLanguage(editorView, "sql"),
        handle: () => {
          if (!editorView) {
            return;
          }
          toggleToLanguage(editorView, "sql");
        },
      },
      {
        icon: <PythonIcon />,
        label: "View as Python",
        // If we're in markdown mode, we should use the markdown hotkey
        hotkey:
          getCurrentLanguageAdapter(editorView) === "markdown"
            ? "cell.viewAsMarkdown"
            : undefined,
        hidden: !canToggleToLanguage(editorView, "python"),
        handle: () => {
          if (!editorView) {
            return;
          }
          maybeAddMarimoImport(autoInstantiate, createCell);
          toggleToLanguage(editorView, "python");
        },
      },
      {
        icon: config.hide_code ? (
          <EyeIcon size={13} strokeWidth={1.5} />
        ) : (
          <EyeOffIcon size={13} strokeWidth={1.5} />
        ),
        label: config.hide_code ? "Show code" : "Hide code",
        handle: toggleHideCode,
        hotkey: "cell.hideCode",
      },
      {
        icon: config.disabled ? (
          <ZapIcon size={13} strokeWidth={1.5} />
        ) : (
          <ZapOffIcon size={13} strokeWidth={1.5} />
        ),
        label: config.disabled ? "Enable cell" : "Disable cell",
        rightElement: (
          <Switch
            data-testid="cell-disable-switch"
            checked={!config.disabled}
            size="sm"
            onCheckedChange={toggleDisabled}
          />
        ),
        handle: toggleDisabled,
      },
    ],

    // Movement
    [
      {
        icon: (
          <MultiIcon>
            <PlusCircleIcon size={13} strokeWidth={1.5} />
            <ChevronUpIcon size={8} strokeWidth={2} />
          </MultiIcon>
        ),
        label: "Create cell above",
        hotkey: "cell.createAbove",
        handle: () => createCell({ cellId, before: true }),
      },
      {
        icon: (
          <MultiIcon>
            <PlusCircleIcon size={13} strokeWidth={1.5} />
            <ChevronDownIcon size={8} strokeWidth={2} />
          </MultiIcon>
        ),
        label: "Create cell below",
        hotkey: "cell.createBelow",
        handle: () => createCell({ cellId, before: false }),
      },
      {
        icon: <ChevronUpIcon size={13} strokeWidth={1.5} />,
        label: "Move cell up",
        hotkey: "cell.moveUp",
        handle: () => moveCell({ cellId, before: true }),
      },
      {
        icon: <ChevronDownIcon size={13} strokeWidth={1.5} />,
        label: "Move cell down",
        hotkey: "cell.moveDown",
        handle: () => moveCell({ cellId, before: false }),
      },
      {
        icon: <ChevronsUpIcon size={13} strokeWidth={1.5} />,
        label: "Send to top",
        hotkey: "cell.sendToTop",
        handle: () => sendToTop({ cellId }),
      },
      {
        icon: <ChevronsDownIcon size={13} strokeWidth={1.5} />,
        label: "Send to bottom",
        hotkey: "cell.sendToBottom",
        handle: () => sendToBottom({ cellId }),
      },
    ],

    // Delete
    [
      {
        label: "Delete",
        hidden: !canDelete,
        variant: "danger",
        icon: <Trash2Icon size={13} strokeWidth={1.5} />,
        handle: () => {
          deleteCell({ cellId });
        },
      },
    ],
  ];

  // remove hidden
  return actions
    .map((group) => group.filter((action) => !action.hidden))
    .filter((group) => group.length > 0);
}
