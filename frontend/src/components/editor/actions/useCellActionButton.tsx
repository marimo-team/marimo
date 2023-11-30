/* Copyright 2023 Marimo. All rights reserved. */
import { downloadCellOutput } from "@/components/export/export-output-button";
import { Switch } from "@/components/ui/switch";
import { formatEditorViews } from "@/core/codemirror/format";
import { useCellActions } from "@/core/cells/cells";
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
} from "lucide-react";
import { ActionButton } from "./types";
import { MultiIcon } from "@/components/icons/multi-icon";
import { CellConfig, CellStatus } from "@/core/cells/types";
import { CellId } from "@/core/cells/ids";
import { saveCellConfig } from "@/core/network/requests";
import { EditorView } from "@codemirror/view";
import { useRunCell } from "../cell/useRunCells";

export interface CellActionButtonProps {
  cellId: CellId;
  status: CellStatus;
  config: CellConfig;
  editorView: EditorView | null;
  hasOutput: boolean;
}

export function useCellActionButtons({
  cellId,
  config,
  editorView,
  hasOutput,
  status,
}: CellActionButtonProps) {
  const {
    createNewCell: createCell,
    updateCellConfig,
    updateCellCode,
    deleteCell,
    moveCell,
    sendToTop,
    sendToBottom,
  } = useCellActions();
  const runCell = useRunCell(cellId);
  const toggleDisabled = async () => {
    if (config.disabled) {
      await saveCellConfig({ configs: { [cellId]: { disabled: false } } });
      updateCellConfig({ cellId, config: { disabled: false } });
    } else {
      await saveCellConfig({ configs: { [cellId]: { disabled: true } } });
      updateCellConfig({ cellId, config: { disabled: true } });
    }
  };

  // Actions
  const actions: ActionButton[][] = [
    [
      {
        icon: <PlayIcon size={13} strokeWidth={1.5} />,
        label: "Run cell",
        hotkey: "cell.run",
        hidden:
          status === "running" ||
          status === "queued" ||
          status === "disabled-transitively" ||
          config.disabled === true,
        handle: () => runCell(),
      },
      {
        icon: <ImageIcon size={13} strokeWidth={1.5} />,
        label: "Export as PNG",
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
        icon: config.disabled ? (
          <ZapIcon size={13} strokeWidth={1.5} />
        ) : (
          <ZapOffIcon size={13} strokeWidth={1.5} />
        ),
        label: config.disabled === true ? "Enable cell" : "Disable cell",
        rightElement: (
          <Switch
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
        variant: "danger",
        icon: <Trash2Icon size={13} strokeWidth={1.5} />,
        handle: () => deleteCell({ cellId }),
      },
    ],
  ];

  // remove hidden
  return actions
    .map((group) => group.filter((action) => !action.hidden))
    .filter((group) => group.length > 0);
}
