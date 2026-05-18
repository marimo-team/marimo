/* Copyright 2026 Marimo. All rights reserved. */

import type { ChatAddToolApproveResponseFunction } from "ai";
import React from "react";
import { logNever } from "@/utils/assertNever";
import type { ToolApproval, ToolState } from "./shared";
import { ToolApprovalCard } from "./tool-approval-card";
import { ToolErrorCard } from "./tool-error-card";
import { ToolHistoryRow } from "./tool-history-row";

interface ToolCallViewProps {
  toolName: string;
  state: ToolState;
  result?: unknown;
  errorText?: string;
  input?: unknown;
  approval?: ToolApproval;
  onApprove?: ChatAddToolApproveResponseFunction;
  index?: number;
  className?: string;
  /**
   * Whether this tool call belongs to the latest message in the conversation.
   * Used by error cards to decide whether to stay expanded (live) or collapse
   * (the user has moved on).
   */
  isLive?: boolean;
}

export const ToolCallView: React.FC<ToolCallViewProps> = ({
  toolName,
  state,
  result,
  errorText,
  input,
  approval,
  onApprove,
  index,
  className,
  isLive = true,
}) => {
  switch (state) {
    case "approval-requested":
      // Approval is a live, blocking action — render it as a prominent card
      // Fall back to history row if the wiring isn't
      // available (shouldn't happen in practice).
      if (approval != null && onApprove != null) {
        return (
          <ToolApprovalCard
            toolName={toolName}
            input={input}
            approval={approval}
            onApprove={onApprove}
            className={className}
          />
        );
      }
      return (
        <ToolHistoryRow
          toolName={toolName}
          state="input-available"
          input={input}
          index={index}
          className={className}
        />
      );

    case "output-error":
      return (
        <ToolErrorCard
          toolName={toolName}
          input={input}
          errorText={errorText}
          isLive={isLive}
          className={className}
        />
      );

    case "input-streaming":
    case "input-available":
    case "approval-responded":
    case "output-available":
    case "output-denied":
      return (
        <ToolHistoryRow
          toolName={toolName}
          state={state}
          input={input}
          result={result}
          approval={approval}
          index={index}
          className={className}
        />
      );

    default:
      logNever(state);
      return null;
  }
};
