/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom, useStore } from "jotai";
import {
  CheckIcon,
  ChevronDownIcon,
  HatGlasses,
  type LucideIcon,
  SparklesIcon,
  WrenchIcon,
} from "lucide-react";
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
import { aiFeaturesEnabledAtom } from "@/core/config/config";
import { getDatasourceContext } from "@/core/ai/context/providers/datasource";
import { getAutoFixes } from "@/core/errors/errors";
import type { MarimoError } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { useOpenAiAssistant } from "../chrome/wrapper/useOpenAiAssistant";
import { type FixMode, useFixMode } from "./fix-mode";

export function buildFixPromptFromText(
  errorText: string,
  cellId?: CellId,
  {
    includeDatasourceContext = false,
  }: { includeDatasourceContext?: boolean } = {},
): string {
  const header =
    cellId != null
      ? `My cell (id: ${cellId}) produced the following error. Please fix it:`
      : "My code gives the following error. Please fix it:";
  let prompt = `${header}\n\n${errorText}`;
  if (cellId != null && includeDatasourceContext) {
    const datasourceContext = getDatasourceContext(cellId);
    if (datasourceContext) {
      prompt += `\n\nDatabase schema: ${datasourceContext}`;
    }
  }
  return prompt;
}

export function buildFixPrompt(errors: MarimoError[], cellId: CellId): string {
  const errorText = errors
    .map((error) => ("msg" in error && error.msg ? error.msg : error.type))
    .join("\n");
  const includeDatasourceContext = errors.some(
    (error) => error.type === "sql-error",
  );
  return buildFixPromptFromText(errorText, cellId, {
    includeDatasourceContext,
  });
}

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
  const aiFeaturesEnabled = useAtomValue(aiFeaturesEnabledAtom);
  const autoFixes = errors.flatMap((error) =>
    getAutoFixes(error, { aiEnabled: aiFeaturesEnabled }),
  );
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const openAiAssistant = useOpenAiAssistant();

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

  const openAISidebar = () => {
    openAiAssistant({
      prompt: buildFixPrompt(errors, cellId),
      submit: false,
      mode: "code_mode",
    });
  };

  return (
    <div className={cn("my-2", className)}>
      {firstFix.fixType === "ai" ? (
        <AIFixButton
          tooltip={firstFix.description}
          openPrompt={() => handleFix(false)}
          applyAutofix={() => handleFix(true)}
          openChat={openAISidebar}
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

interface FixModeConfig {
  Icon: LucideIcon;
  title: string;
  description: string;
}

const MODE_CONFIG: Record<FixMode, FixModeConfig> = {
  autofix: {
    Icon: WrenchIcon,
    title: "Inline AI Fix",
    description: "Apply AI fixes inline in the cell",
  },
  chat: {
    Icon: HatGlasses,
    title: "Fix with AI assistant",
    description: "Open the AI sidebar to fix",
  },
  prompt: {
    Icon: SparklesIcon,
    title: "Suggest a prompt",
    description: "Edit the prompt before applying",
  },
};

const FIX_MODES: FixMode[] = ["autofix", "prompt", "chat"];

export const AIFixButton = ({
  tooltip,
  openPrompt,
  applyAutofix,
  openChat,
}: {
  tooltip: string;
  openPrompt: () => void;
  applyAutofix: () => void;
  openChat: () => void;
}) => {
  const { fixMode, setFixMode } = useFixMode();

  let onAction = openPrompt;
  if (fixMode === "chat") {
    onAction = openChat;
  } else if (fixMode === "autofix") {
    onAction = applyAutofix;
  }
  const { Icon, title } = MODE_CONFIG[fixMode];

  return (
    <div className="flex">
      <Tooltip content={tooltip} align="start">
        <Button
          size="xs"
          variant="outline"
          className="font-normal rounded-r-none border-r-0"
          onClick={onAction}
        >
          <Icon className="h-3 w-3 mr-2 mb-0.5" />
          {title}
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
          {FIX_MODES.map((mode) => (
            <DropdownMenuItem
              key={mode}
              className="flex items-center gap-2"
              onClick={() => setFixMode(mode)}
            >
              <AiModeItem mode={mode} selected={mode === fixMode} />
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};

const AiModeItem = ({
  mode,
  selected,
}: {
  mode: FixMode;
  selected: boolean;
}) => {
  const { Icon, title, description } = MODE_CONFIG[mode];

  return (
    <div className="flex items-center gap-2 w-full">
      <Icon className="h-4 w-4 shrink-0" />
      <div className="flex flex-col">
        <span className="font-medium">{title}</span>
        <span className="text-xs text-muted-foreground">{description}</span>
      </div>
      {selected && <CheckIcon className="h-4 w-4 ml-auto shrink-0" />}
    </div>
  );
};
