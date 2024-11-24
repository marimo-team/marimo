/* Copyright 2024 Marimo. All rights reserved. */
import React, { Fragment } from "react";
import {
  type CellActionButtonProps,
  useCellActionButtons,
} from "../actions/useCellActionButton";
import {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
} from "@/components/ui/context-menu";
import { renderMinimalShortcut } from "@/components/shortcuts/renderShortcut";
import type { ActionButton } from "../actions/types";
import {
  ClipboardPasteIcon,
  CopyIcon,
  ImageIcon,
  ScissorsIcon,
  SearchIcon,
} from "lucide-react";
import { goToDefinitionAtCursorPosition } from "@/core/codemirror/go-to-definition/utils";
import { CellOutputId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

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
      icon: <CopyIcon size={13} strokeWidth={1.5} />,
      handle: () => {
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
        navigator.clipboard.writeText(output.textContent ?? "");
      },
    },
    {
      label: "Cut",
      icon: <ScissorsIcon size={13} strokeWidth={1.5} />,
      handle: () => {
        document.execCommand("cut");
      },
    },
    {
      label: "Paste",
      icon: <ClipboardPasteIcon size={13} strokeWidth={1.5} />,
      handle: async () => {
        const { getEditorView } = props;
        const editorView = getEditorView();
        if (!editorView) {
          return;
        }
        // We can't use the native browser paste since we don't have focus
        // so instead we use the editorViewView
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
      <ContextMenuContent className="w-[300px]">
        {[DEFAULT_CONTEXT_MENU_ITEMS, ...actions].map((group, i) => (
          <Fragment key={i}>
            {group.map((action) => {
              if (action.hidden) {
                return null;
              }
              return (
                <ContextMenuItem
                  key={action.label}
                  onSelect={(evt) => {
                    action.handle(evt);
                  }}
                  variant={action.variant}
                >
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
                </ContextMenuItem>
              );
            })}
            {i < group.length - 1 && <ContextMenuSeparator />}
          </Fragment>
        ))}
      </ContextMenuContent>
    </ContextMenu>
  );
};
