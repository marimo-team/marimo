/* Copyright 2024 Marimo. All rights reserved. */
import { DatabaseIcon, DiamondPlusIcon, PlusIcon } from "lucide-react";
import { Button } from "@/components/editor/inputs/Inputs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { maybeAddMarimoImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { LanguageAdapters } from "@/core/codemirror/language/LanguageAdapters";
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
  onClick: ((opts: { code: string; hideCode?: boolean }) => void) | undefined;
}) => {
  const { createNewCell, addSetupCellIfDoesntExist } = useCellActions();

  const baseTooltipContent =
    getConnectionTooltip(connectionState) || tooltipContent;
  const finalTooltipContent = isAppInteractionDisabled(connectionState) ? (
    baseTooltipContent
  ) : (
    <div>{baseTooltipContent}</div>
  );

  const addPythonCell = () => {
    onClick?.({ code: "" });
  };

  // NB: When adding the marimo import for markdown and SQL, we run it
  // automatically regardless of whether autoinstantiate or lazy execution is
  // enabled; the user experience is confusing otherwise (how does the user
  // know they need to run import marimo as mo. first?).
  const addMarkdownCell = () => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    onClick?.({
      code: LanguageAdapters.markdown.defaultCode,
      hideCode: true,
    });
  };

  const addSQLCell = () => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    onClick?.({ code: LanguageAdapters.sql.defaultCode });
  };

  const addSetupCell = () => {
    addSetupCellIfDoesntExist({});
  };

  const renderIcon = (icon: React.ReactNode) => {
    return <div className="mr-3 text-muted-foreground">{icon}</div>;
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button
          className={cn(
            "shoulder-button hover-action border-none shadow-none! bg-transparent! focus-visible:outline-none",
            isAppInteractionDisabled(connectionState) && " inactive-button",
          )}
          onMouseDown={Events.preventFocus}
          size="small"
          color="hint-green"
          data-testid="create-cell-button"
        >
          <Tooltip content={finalTooltipContent}>
            <PlusIcon
              strokeWidth={3.2}
              size={16}
              className="opacity-60 hover:opacity-90"
            />
          </Tooltip>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={addPythonCell}>
          {renderIcon(<PythonIcon />)}
          Python cell
        </DropdownMenuItem>
        <DropdownMenuItem onClick={addMarkdownCell}>
          {renderIcon(<MarkdownIcon />)}
          Markdown cell
        </DropdownMenuItem>
        <DropdownMenuItem onClick={addSQLCell}>
          {renderIcon(<DatabaseIcon size={13} strokeWidth={1.5} />)}
          SQL cell
        </DropdownMenuItem>
        <DropdownMenuItem onClick={addSetupCell}>
          {renderIcon(<DiamondPlusIcon size={13} strokeWidth={1.5} />)}
          Setup cell
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
