/* Copyright 2024 Marimo. All rights reserved. */

import {
  ClipboardCopyIcon,
  ClipboardPasteIcon,
  CopyIcon,
  ImageIcon,
  ScissorsIcon,
  SearchIcon,
} from "lucide-react";
import React, { Fragment } from "react";
import { renderMinimalShortcut } from "@/components/shortcuts/renderShortcut";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { CellOutputId } from "@/core/cells/ids";
import { goToDefinitionAtCursorPosition } from "@/core/codemirror/go-to-definition/utils";
import { sendToPanelManager } from "@/core/vscode/vscode-bindings";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import type { ActionButton } from "../actions/types";
import {
  type CellActionButtonProps,
  useCellActionButtons,
} from "../actions/useCellActionButton";

interface Props extends CellActionButtonProps {
  children: React.ReactNode;
}

export const CellActionsContextMenu = ({ children, ...props }: Props) => {
  const actions = useCellActionButtons({ cell: props });
  const [imageRightClicked, setImageRightClicked] =
    React.useState<HTMLImageElement>();

  const DEFAULT_CONTEXT_MENU_ITEMS: ActionButton[] = [
    {
      label: "Copy",
      hidden: Boolean(imageRightClicked),
      icon: <CopyIcon size={13} strokeWidth={1.5} />,
      handle: async () => {
        // Has selection, use browser copy
        const hasSelection = window.getSelection()?.toString();
        if (hasSelection) {
          document.execCommand("copy");
          return;
        }

        // No selection, copy the full cell output
        const output = document.getElementById(
          CellOutputId.create(props.cellId),
        );
        if (!output) {
          Logger.warn("cell-context-menu: output not found");
          return;
        }
        // Copy the output of the cell
        await copyToClipboard(output.textContent ?? "");
      },
    },
    {
      label: "Cut",
      hidden: Boolean(imageRightClicked),
      icon: <ScissorsIcon size={13} strokeWidth={1.5} />,
      handle: () => {
        document.execCommand("cut");
      },
    },
    {
      label: "Paste",
      hidden: Boolean(imageRightClicked),
      icon: <ClipboardPasteIcon size={13} strokeWidth={1.5} />,
      handle: async () => {
        const { getEditorView } = props;
        const editorView = getEditorView();
        if (!editorView) {
          return;
        }
        // We can't use the native browser paste since we don't have focus
        // so instead we use the editorViewView
        try {
          const clipText = await navigator.clipboard.readText();
          if (clipText) {
            // Get the current selection, or the start of the document if nothing is selected
            const { from, to } = editorView.state.selection.main;
            // Create a new transaction that replaces the selection with the clipboard text
            const tr = editorView.state.update({
              changes: { from, to, insert: clipText },
            });
            // Apply the transaction
            editorView.dispatch(tr);
          }
        } catch (error) {
          Logger.error("Failed to paste from clipboard", error);
          // Try vscode or other parent
          sendToPanelManager({ command: "paste" });
        }
      },
    },
    {
      label: "Copy image",
      hidden: !imageRightClicked,
      icon: <ClipboardCopyIcon size={13} strokeWidth={1.5} />,
      handle: async () => {
        if (imageRightClicked) {
          const response = await fetch(imageRightClicked.src);
          const blob = await response.blob();
          const item = new ClipboardItem({ [blob.type]: blob });
          await navigator.clipboard
            .write([item])
            .then(() => {
              toast({
                title: "Copied image to clipboard",
              });
            })
            .catch((error) => {
              toast({
                title:
                  "Failed to copy image to clipboard. Try downloading instead.",
                description: error.message,
              });
              Logger.error("Failed to copy image to clipboard", error);
            });
        }
      },
    },
    {
      icon: <ImageIcon size={13} strokeWidth={1.5} />,
      label: "Download image",
      hidden: !imageRightClicked,
      handle: () => {
        if (imageRightClicked) {
          const link = document.createElement("a");
          link.download = "image.png";
          link.href = imageRightClicked.src;
          link.click();
        }
      },
    },
    {
      label: "Go to Definition",
      icon: <SearchIcon size={13} strokeWidth={1.5} />,
      handle: () => {
        const { getEditorView } = props;
        const editorView = getEditorView();
        if (editorView) {
          goToDefinitionAtCursorPosition(editorView);
        }
      },
    },
  ];

  const allActions: ActionButton[][] = [DEFAULT_CONTEXT_MENU_ITEMS, ...actions];

  return (
    <ContextMenu>
      <ContextMenuTrigger
        onContextMenu={(evt) => {
          if (evt.target instanceof HTMLImageElement) {
            setImageRightClicked(evt.target);
          } else {
            setImageRightClicked(undefined);
          }
        }}
        asChild={true}
      >
        {children}
      </ContextMenuTrigger>
      <ContextMenuContent className="w-[300px]" scrollable={true}>
        {allActions.map((group, i) => (
          <Fragment key={i}>
            {group.map((action) => {
              if (action.hidden) {
                return null;
              }

              let body = (
                <div className="flex items-center flex-1">
                  {action.icon && (
                    <div className="mr-2 w-5 text-muted-foreground">
                      {action.icon}
                    </div>
                  )}
                  <div className="flex-1">{action.label}</div>
                  <div className="flex-shrink-0 text-sm">
                    {action.hotkey && renderMinimalShortcut(action.hotkey)}
                    {action.rightElement}
                  </div>
                </div>
              );

              if (action.tooltip) {
                body = (
                  <Tooltip delayDuration={100} content={action.tooltip}>
                    {body}
                  </Tooltip>
                );
              }

              return (
                <ContextMenuItem
                  key={action.label}
                  className={action.disabled ? "!opacity-50" : ""}
                  onSelect={(evt) => {
                    if (action.disableClick || action.disabled) {
                      return;
                    }
                    action.handle(evt);
                  }}
                  variant={action.variant}
                >
                  {body}
                </ContextMenuItem>
              );
            })}
            {i < allActions.length - 1 && <ContextMenuSeparator />}
          </Fragment>
        ))}
      </ContextMenuContent>
    </ContextMenu>
  );
};
