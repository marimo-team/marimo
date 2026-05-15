/* Copyright 2026 Marimo. All rights reserved. */

import { BanIcon, CheckCircleIcon, Loader2, WrenchIcon } from "lucide-react";
import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { formatToolName, type ToolApproval, type ToolState } from "./shared";
import { ToolArgsRenderer } from "./tool-args";
import { ResultRenderer } from "./tool-result";

// States considered "inert" — they represent past or background work that the
// user does not need to act on.
export type HistoryState = Exclude<
  ToolState,
  "approval-requested" | "output-error"
>;

const STATUS_LABEL: Record<HistoryState, string> = {
  "input-streaming": "Generating",
  "input-available": "Running",
  "approval-responded": "Awaiting result",
  "output-available": "Done",
  "output-denied": "Denied",
};

const StatusIcon: React.FC<{ state: HistoryState }> = ({ state }) => {
  switch (state) {
    case "input-streaming":
    case "input-available":
    case "approval-responded":
      return <Loader2 className="h-3 w-3 animate-spin" />;
    case "output-available":
      return <CheckCircleIcon className="h-3 w-3 text-(--grass-11)" />;
    case "output-denied":
      return <BanIcon className="h-3 w-3 text-muted-foreground" />;
    default:
      logNever(state);
      return <WrenchIcon className="h-3 w-3" />;
  }
};

function getTriggerToneClass(state: HistoryState): string {
  switch (state) {
    case "output-available":
      return "text-(--grass-11)/80";
    case "output-denied":
      return "text-muted-foreground";
    case "input-streaming":
    case "input-available":
    case "approval-responded":
      return "";
    default:
      logNever(state);
      return "";
  }
}

interface ToolHistoryRowProps {
  toolName: string;
  state: HistoryState;
  input: unknown;
  result?: unknown;
  approval?: ToolApproval;
  index?: number;
  className?: string;
}

export const ToolHistoryRow: React.FC<ToolHistoryRowProps> = ({
  toolName,
  state,
  input,
  result,
  approval,
  index = 0,
  className,
}) => {
  return (
    <Accordion
      key={`tool-${index}`}
      type="single"
      collapsible={true}
      className={cn("w-full", className)}
    >
      <AccordionItem value="tool-call" className="border-0">
        <AccordionTrigger
          className={cn(
            "h-6 text-xs border-border shadow-none! ring-0! bg-muted/60 hover:bg-muted py-0 px-2 gap-1 rounded-sm [&[data-state=open]>svg]:rotate-180 hover:no-underline",
            getTriggerToneClass(state),
          )}
        >
          <span className="flex items-center gap-1">
            <StatusIcon state={state} />
            {STATUS_LABEL[state]}:
            <code className="font-mono text-xs">
              {formatToolName(toolName)}
            </code>
          </span>
        </AccordionTrigger>
        <AccordionContent className="py-2 px-2">
          <HistoryContent
            state={state}
            input={input}
            result={result}
            approval={approval}
          />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

const HistoryContent: React.FC<{
  state: HistoryState;
  input: unknown;
  result?: unknown;
  approval?: ToolApproval;
}> = ({ state, input, result, approval }) => {
  switch (state) {
    case "input-streaming":
    case "input-available":
    case "approval-responded":
      return <ToolArgsRenderer input={input} />;

    case "output-available":
      return (
        <div className="space-y-3">
          <ToolArgsRenderer input={input} />
          {result != null && <ResultRenderer result={result} />}
        </div>
      );

    case "output-denied":
      return (
        <div className="space-y-3">
          <ToolArgsRenderer input={input} />
          <div className="bg-muted/40 border border-border rounded-md p-3 text-xs text-muted-foreground leading-relaxed">
            Tool execution was denied
            {approval?.reason ? `: ${approval.reason}` : "."}
          </div>
        </div>
      );

    default:
      logNever(state);
      return null;
  }
};
