/* Copyright 2026 Marimo. All rights reserved. */

import type { ChatAddToolApproveResponseFunction } from "ai";
import React from "react";
import type { ToolApproval, ToolState } from "./shared";
import { ToolApprovalCard } from "./tool-approval-card";
import { ToolStep } from "./tool-step";

interface ToolCallViewProps {
  toolName: string;
  state: ToolState;
  result?: unknown;
  errorText?: string;
  input?: unknown;
  approval?: ToolApproval;
  onApprove?: ChatAddToolApproveResponseFunction;
  className?: string;
  isActive?: boolean;
}

export const ToolCallView: React.FC<ToolCallViewProps> = ({
  toolName,
  state,
  approval,
  onApprove,
  ...props
}) => {
  if (state === "approval-requested") {
    return approval != null && onApprove != null ? (
      <ToolApprovalCard
        toolName={toolName}
        input={props.input}
        approval={approval}
        onApprove={onApprove}
        className={props.className}
      />
    ) : (
      <ToolStep {...props} toolName={toolName} state="input-available" />
    );
  }
  return (
    <ToolStep
      {...props}
      toolName={toolName}
      state={state}
      approval={approval}
    />
  );
};
