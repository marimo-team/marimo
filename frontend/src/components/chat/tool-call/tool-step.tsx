/* Copyright 2026 Marimo. All rights reserved. */

import {
  BanIcon,
  ChevronRightIcon,
  CircleSlashIcon,
  Loader2Icon,
  type LucideIcon,
  XCircleIcon,
} from "lucide-react";
import React from "react";
import { cn } from "@/utils/cn";
import {
  PENDING_TOOL_STATES,
  type ToolApproval,
  type ToolState,
} from "./shared";
import { ToolArgsRenderer } from "./tool-args";
import { describeToolCall } from "./tool-labels";
import { ResultRenderer } from "./tool-result";

type ToolStepState = Exclude<ToolState, "approval-requested">;

interface ToolStepProps {
  toolName: string;
  state: ToolStepState;
  input?: unknown;
  result?: unknown;
  errorText?: string;
  approval?: ToolApproval;
  isActive?: boolean;
  className?: string;
}

export const ToolStep: React.FC<ToolStepProps> = ({
  toolName,
  state,
  input,
  result,
  errorText,
  approval,
  isActive = true,
  className,
}) => {
  const [open, setOpen] = React.useState(false);
  const pending = PENDING_TOOL_STATES.has(state);
  const { label, detail, icon } = describeToolCall(
    toolName,
    input,
    pending ? "running" : "done",
  );
  const status = getStatus(state, pending && !isActive, icon);
  const failed = state === "output-error";

  return (
    <div className={cn("w-full", className)}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        className={cn(
          "group/step -mx-1.5 flex w-fit max-w-full min-w-0 items-center gap-1.5 rounded-md px-1.5 py-0.5 text-left text-xs leading-4 text-muted-foreground transition-colors hover:bg-foreground/6 hover:text-foreground focus-visible:outline-1 focus-visible:outline-(--slate-8)",
          open && "text-foreground",
          failed && "text-(--red-11) hover:bg-(--red-3) hover:text-(--red-11)",
        )}
      >
        <status.icon
          aria-hidden={true}
          className={cn(
            // Offsets lucide's built-in padding.
            "-ml-px size-3 shrink-0",
            status.spinning && "animate-spin",
          )}
        />
        <span className="shrink-0">{label}</span>
        {detail && (
          <code className="min-w-0 truncate font-mono text-[0.6875rem] opacity-80">
            {detail}
          </code>
        )}
        {status.suffix && (
          <span className="shrink-0 opacity-80">· {status.suffix}</span>
        )}
        <ChevronRightIcon
          aria-hidden={true}
          className={cn(
            "size-3 shrink-0 opacity-40 transition-transform group-hover/step:opacity-100",
            open && "rotate-90 opacity-100",
          )}
        />
      </button>
      {open && (
        <ToolStepDetails
          state={state}
          input={input}
          result={result}
          errorText={errorText}
          approval={approval}
        />
      )}
    </div>
  );
};

function getStatus(
  state: ToolStepState,
  interrupted: boolean,
  doneIcon: LucideIcon,
): { icon: LucideIcon; suffix?: string; spinning?: boolean } {
  if (interrupted) {
    return { icon: CircleSlashIcon, suffix: "Stopped" };
  }
  switch (state) {
    case "output-error":
      return { icon: XCircleIcon, suffix: "Failed" };
    case "output-denied":
      return { icon: BanIcon, suffix: "Denied" };
    case "output-available":
      return { icon: doneIcon };
    default:
      return { icon: Loader2Icon, spinning: true };
  }
}

const ToolStepDetails: React.FC<
  Pick<ToolStepProps, "state" | "input" | "result" | "errorText" | "approval">
> = ({ state, input, result, errorText, approval }) => (
  <div className="mt-1 mb-2 ml-5.5 space-y-3">
    <ToolArgsRenderer input={input} />
    {state === "output-available" && result != null && (
      <ResultRenderer result={result} />
    )}
    {state === "output-error" && errorText && (
      <pre className="max-h-64 overflow-auto rounded border border-(--red-6) bg-(--red-2) p-2 text-xs leading-relaxed whitespace-pre-wrap text-(--red-11) scrollbar-thin">
        {errorText}
      </pre>
    )}
    {state === "output-denied" && (
      <p className="text-xs text-muted-foreground">
        Tool execution was denied
        {approval?.reason ? `: ${approval.reason}` : "."}
      </p>
    )}
  </div>
);
