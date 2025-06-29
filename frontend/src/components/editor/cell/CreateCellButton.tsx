/* Copyright 2024 Marimo. All rights reserved. */
import { DatabaseIcon, PlusIcon } from "lucide-react";
import { Button } from "@/components/editor/inputs/Inputs";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql";
import {
  getConnectionTooltip,
  isAppInteractionDisabled,
} from "@/core/websocket/connection-utils";
import type { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { Tooltip } from "../../ui/tooltip";
import { MarkdownIcon, PythonIcon } from "./code/icons";

export const CreateCellButton = ({
  connectionState,
  onClick,
  tooltipContent,
}: {
  connectionState: WebSocketState;
  tooltipContent: React.ReactNode;
  onClick: ((opts: { code: string }) => void) | undefined;
}) => {
  const baseTooltipContent = getConnectionTooltip(connectionState) || tooltipContent;
  const finalTooltipContent = isAppInteractionDisabled(connectionState) ? baseTooltipContent : (
    <div className="flex flex-col gap-4">
      <div>{baseTooltipContent}</div>
      <div className="text-xs text-muted-foreground font-medium pt-1 -mt-2 border-t border-border">
        Right-click for cell types
      </div>
    </div>
  );

  return (
    <CreateCellButtonContextMenu onClick={onClick}>
      <Tooltip content={finalTooltipContent} usePortal={false}>
        <Button
          onClick={() => onClick?.({ code: "" })}
          className={cn(
            "shoulder-button hover-action",
            isAppInteractionDisabled(connectionState) && " inactive-button",
          )}
          onMouseDown={Events.preventFocus}
          shape="circle"
          size="small"
          color="hint-green"
          data-testid="create-cell-button"
        >
          <PlusIcon strokeWidth={1.8} />
        </Button>
      </Tooltip>
    </CreateCellButtonContextMenu>
  );
};

const CreateCellButtonContextMenu = (props: {
  onClick: ((opts: { code: string }) => void) | undefined;
  children: React.ReactNode;
}) => {
  const { children, onClick } = props;

  if (!onClick) {
    return children;
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger>{children}</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem
          key="python"
          onSelect={(evt) => {
            evt.stopPropagation();
            onClick({ code: "" });
          }}
        >
          <div className="mr-3 text-muted-foreground">
            <PythonIcon />
          </div>
          Python cell
        </ContextMenuItem>

        <ContextMenuItem
          key="markdown"
          onSelect={(evt) => {
            evt.stopPropagation();
            onClick({ code: new MarkdownLanguageAdapter().defaultCode });
          }}
        >
          <div className="mr-3 text-muted-foreground">
            <MarkdownIcon />
          </div>
          Markdown cell
        </ContextMenuItem>
        <ContextMenuItem
          key="sql"
          onSelect={(evt) => {
            evt.stopPropagation();
            onClick({ code: new SQLLanguageAdapter().defaultCode });
          }}
        >
          <div className="mr-3 text-muted-foreground">
            <DatabaseIcon size={13} strokeWidth={1.5} />
          </div>
          SQL cell
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
};
