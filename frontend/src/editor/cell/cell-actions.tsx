/* Copyright 2023 Marimo. All rights reserved. */
import { Fragment, PropsWithChildren, useState } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  TooltipContent,
  TooltipRoot,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useCellActions } from "@/core/state/cells";
import { CellId } from "@/core/model/ids";
import { MultiIcon } from "@/components/icons/multi-icon";
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronsDownIcon,
  ChevronsUpIcon,
  Code2Icon,
  FocusIcon,
  ImageIcon,
  PlusCircleIcon,
  Trash2Icon,
  ZapIcon,
  ZapOffIcon,
} from "lucide-react";
import { downloadCellOutput } from "@/components/export/export-output-button";
import { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { EditorView } from "codemirror";
import { formatEditorViews } from "@/core/codemirror/format";
import { cn } from "@/lib/utils";
import { renderMinimalShortcut } from "@/components/shortcuts/renderShortcut";
import { CellConfig } from "@/core/model/cells";
import { Switch } from "@/components/ui/switch";
import React from "react";
import { saveCellConfig } from "@/core/network/requests";

interface Props {
  editorView: EditorView | null;
  hasOutput: boolean;
  cellId: CellId;
  config: CellConfig;
}

interface Action {
  label: string;
  variant?: "danger";
  hotkey?: HotkeyAction;
  icon?: React.ReactNode;
  hidden?: boolean;
  rightElement?: React.ReactNode;
  handle: () => void;
}

export const CellActionsDropdown = ({
  cellId,
  children,
  hasOutput,
  editorView,
  config,
}: PropsWithChildren<Props>) => {
  const [open, setOpen] = useState(false);
  const {
    createNewCell: createCell,
    updateCellConfig,
    updateCellCode,
    deleteCell,
    focusCell,
    moveCell,
    sendToTop,
    sendToBottom,
  } = useCellActions();
  const toggleDisabled = async () => {
    if (config.disabled) {
      await saveCellConfig({ configs: { [cellId]: { disabled: false } } });
      updateCellConfig({ cellId, config: { disabled: false } });
    } else {
      await saveCellConfig({ configs: { [cellId]: { disabled: true } } });
      updateCellConfig({ cellId, config: { disabled: true } });
    }
  };

  const actions: Action[][] = [
    // Actions
    [
      {
        icon: <ImageIcon size={13} strokeWidth={1.5} />,
        label: "Export to PNG",
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
        icon: (
          <MultiIcon>
            <FocusIcon size={13} strokeWidth={1.5} />
            <ChevronUpIcon size={8} strokeWidth={2} />
          </MultiIcon>
        ),
        label: "Focus cell above",
        hotkey: "cell.focusUp",
        handle: () => focusCell({ cellId, before: true }),
      },
      {
        icon: (
          <MultiIcon>
            <FocusIcon size={13} strokeWidth={1.5} />
            <ChevronDownIcon size={8} strokeWidth={2} />
          </MultiIcon>
        ),
        label: "Focus cell below",
        hotkey: "cell.focusDown",
        handle: () => focusCell({ cellId, before: false }),
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

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <TooltipRoot delayDuration={400} disableHoverableContent={true}>
        {!open && (
          <TooltipContent className="w-full bg-card" tabIndex={-1}>
            <div className="text-foreground-muted flex flex-col text-center">
              <span>
                <span className="text-foreground font-semibold">Drag </span>to
                move cell
              </span>
              <span>
                <span className="text-foreground font-semibold">Click </span>to
                open menu
              </span>
            </div>
          </TooltipContent>
        )}
        <TooltipTrigger>
          <PopoverTrigger className="flex">{children}</PopoverTrigger>
        </TooltipTrigger>
      </TooltipRoot>
      <PopoverContent
        className="w-[300px] p-0 pt-1"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <Command>
          <CommandInput
            placeholder="Search actions..."
            className="h-6 m-1"
            autoFocus={true}
          />
          <CommandEmpty>No results</CommandEmpty>
          {actions.map((group, i) => (
            <Fragment key={i}>
              <CommandGroup key={i}>
                {group.map((action) => {
                  if (action.hidden) {
                    return null;
                  }
                  return (
                    <CommandItem
                      key={action.label}
                      onSelect={() => {
                        action.handle();
                        setOpen(false);
                      }}
                      className={cn(
                        action.variant === "danger" &&
                          "aria-selected:bg-[var(--red-5)] aria-selected:text-[var(--red-12)]"
                      )}
                    >
                      <div className="flex items-center flex-1">
                        {action.icon && (
                          <div className="mr-2 w-5">{action.icon}</div>
                        )}
                        <div className="flex-1">{action.label}</div>
                        <div className="flex-shrink-0 text-sm">
                          {action.hotkey &&
                            renderMinimalShortcut(action.hotkey)}
                          {action.rightElement}
                        </div>
                      </div>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              {i < actions.length - 1 && <CommandSeparator />}
            </Fragment>
          ))}
        </Command>
      </PopoverContent>
    </Popover>
  );
};
