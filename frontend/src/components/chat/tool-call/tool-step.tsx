/* Copyright 2026 Marimo. All rights reserved. */

import {
  BanIcon,
  ChevronRightIcon,
  CircleSlashIcon,
  Loader2Icon,
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

/** Every state except a pending approval, which needs its own card. */
type ToolStepState = Exclude<ToolState, "approval-requested">;

interface ToolStepProps {
  toolName: string;
  state: ToolStepState;
  input?: unknown;
  result?: unknown;
  errorText?: string;
  approval?: ToolApproval;
  /** Whether the turn this step belongs to is still running. */
  isActive?: boolean;
  className?: string;
}

/** One tool call in the activity timeline; expands to show input and output. */
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
  const interrupted = pending && !isActive;
  const {
    label,
    detail,
    icon: Icon,
  } = describeToolCall(toolName, input, pending ? "running" : "done");

  const status = interrupted
    ? { icon: CircleSlashIcon, suffix: "Stopped" }
    : state === "output-error"
      ? { icon: XCircleIcon, suffix: "Failed" }
      : state === "output-denied"
        ? { icon: BanIcon, suffix: "Denied" }
        : pending
          ? { icon: Loader2Icon, suffix: undefined }
          : { icon: Icon, suffix: undefined };
  const StatusIcon = status.icon;
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
        <StatusIcon
          aria-hidden={true}
          className={cn(
            // Offset lucide's built-in padding so the glyph lines up with
            // the prose above and below.
            "-ml-px size-3 shrink-0",
            pending && !interrupted && "animate-spin",
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
      )}
    </div>
  );
};
