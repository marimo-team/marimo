/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom, useStore } from "jotai";
import { ChevronDownIcon, SparklesIcon, WrenchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { notebookAtom, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { aiEnabledAtom } from "@/core/config/config";
import { getAutoFixes } from "@/core/errors/errors";
import type { MarimoError } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { type FixMode, useFixMode } from "./fix-mode";

export const AutoFixButton = ({
  errors,
  cellId,
  className,
}: {
  errors: MarimoError[];
  cellId: CellId;
  className?: string;
}) => {
  const store = useStore();
  const { createNewCell } = useCellActions();
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const autoFixes = errors.flatMap((error) =>
    getAutoFixes(error, { aiEnabled }),
  );
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);

  if (autoFixes.length === 0) {
    return null;
  }

  // TODO: Add a dropdown menu with the auto-fixes, when we need to support
  // multiple fixes.
  const firstFix = autoFixes[0];

  const handleFix = (triggerFix: boolean) => {
    const editorView =
      store.get(notebookAtom).cellHandles[cellId].current?.editorView;
    firstFix.onFix({
      addCodeBelow: (code: string) => {
        createNewCell({
          cellId: cellId,
          autoFocus: false,
          before: false,
          code: code,
        });
      },
      editor: editorView,
      cellId: cellId,
      aiFix: {
        setAiCompletionCell,
        triggerFix,
      },
    });
    // Focus the editor
    editorView?.focus();
  };

  return (
    <div className={cn("my-2", className)}>
      {firstFix.fixType === "ai" ? (
        <AIFixButton
          tooltip={firstFix.description}
          openPrompt={() => handleFix(false)}
          applyAutofix={() => handleFix(true)}
        />
      ) : (
        <Tooltip content={firstFix.description} align="start">
          <Button
            size="xs"
            variant="outline"
            className="font-normal"
            onClick={() => handleFix(false)}
          >
            <WrenchIcon className="h-3 w-3 mr-2" />
            {firstFix.title}
          </Button>
        </Tooltip>
      )}
    </div>
  );
};

const PromptIcon = SparklesIcon;
const AutofixIcon = WrenchIcon;

const PromptTitle = "Suggest a prompt";
const AutofixTitle = "Fix with AI";

export const AIFixButton = ({
  tooltip,
  openPrompt,
  applyAutofix,
}: {
  tooltip: string;
  openPrompt: () => void;
  applyAutofix: () => void;
}) => {
  const { fixMode, setFixMode } = useFixMode();

  return (
    <div className="flex">
      <Tooltip content={tooltip} align="start">
        <Button
          size="xs"
          variant="outline"
          className="font-normal rounded-r-none border-r-0"
          onClick={fixMode === "prompt" ? openPrompt : applyAutofix}
        >
          {fixMode === "prompt" ? (
            <PromptIcon className="h-3 w-3 mr-2 mb-0.5" />
          ) : (
            <AutofixIcon className="h-3 w-3 mr-2 mb-0.5" />
          )}
          {fixMode === "prompt" ? PromptTitle : AutofixTitle}
        </Button>
      </Tooltip>
      <DropdownMenu>
        <DropdownMenuTrigger asChild={true}>
          <Button
            size="xs"
            variant="outline"
            className="rounded-l-none px-2"
            aria-label="Fix options"
          >
            <ChevronDownIcon className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem
            className="flex items-center gap-2"
            onClick={() => {
              setFixMode(fixMode === "prompt" ? "autofix" : "prompt");
            }}
          >
            <AiModeItem mode={fixMode === "prompt" ? "autofix" : "prompt"} />
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

const AiModeItem = ({ mode }: { mode: FixMode }) => {
  const icon =
    mode === "prompt" ? (
      <PromptIcon className="h-4 w-4" />
    ) : (
      <AutofixIcon className="h-4 w-4" />
    );
  const title = mode === "prompt" ? PromptTitle : AutofixTitle;
  const description =
    mode === "prompt"
      ? "Edit the prompt before applying"
      : "Apply AI fixes automatically";

  return (
    <div className="flex items-center gap-2">
      {icon}
      <div className="flex flex-col">
        <span className="font-medium">{title}</span>
        <span className="text-xs text-muted-foreground">{description}</span>
      </div>
    </div>
  );
};
