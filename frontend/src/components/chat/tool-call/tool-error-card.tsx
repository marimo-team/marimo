/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronDownIcon, XCircleIcon } from "lucide-react";
import React from "react";
import { cn } from "@/utils/cn";
import { formatToolName } from "./shared";
import { ToolArgsRenderer } from "./tool-args";

interface ToolErrorCardProps {
  toolName: string;
  input: unknown;
  errorText?: string;
  // When false, defaults to collapsed (the conversation has moved past this).
  isLive: boolean;
  className?: string;
}

export const ToolErrorCard: React.FC<ToolErrorCardProps> = ({
  toolName,
  input,
  errorText,
  isLive,
  className,
}) => {
  const [open, setOpen] = React.useState(isLive);

  // Auto-collapse once when the conversation moves past this turn.
  // The user can still re-open manually afterwards; we only do this on the
  // live → not-live transition, never the reverse.
  const wasLive = React.useRef(isLive);
  React.useEffect(() => {
    if (wasLive.current && !isLive) {
      setOpen(false);
    }
    wasLive.current = isLive;
  }, [isLive]);

  return (
    <div
      className={cn(
        "rounded-md border border-(--red-6) bg-(--red-2)",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-(--red-11) hover:bg-(--red-3) rounded-md transition-colors"
        aria-expanded={open}
      >
        <XCircleIcon className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1 text-left">
          <span className="font-semibold">Failed:</span>{" "}
          <code className="font-mono">{formatToolName(toolName)}</code>
        </span>
        <ChevronDownIcon
          className={cn(
            "h-3.5 w-3.5 shrink-0 transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3 border-t border-(--red-6)/40 pt-3">
          <ToolArgsRenderer input={input} />
          {errorText && (
            <div>
              <h3 className="text-xs font-semibold text-(--red-11) mb-1">
                Error
              </h3>
              <pre className="bg-(--red-2) border border-(--red-6) rounded p-2 text-xs text-(--red-11) leading-relaxed overflow-auto scrollbar-thin max-h-64 whitespace-pre-wrap">
                {errorText}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
