/* Copyright 2026 Marimo. All rights reserved. */

import type { ToolUIPart } from "ai";

export type ToolState = ToolUIPart["state"];

// The AI SDK declares `approval` inline on every variant of `UIToolInvocation`
// rather than exporting a named type, so we derive ours from there.
export type ToolApproval = NonNullable<ToolUIPart["approval"]>;

/** States in which a tool call has started but not produced a result. */
export const PENDING_TOOL_STATES: ReadonlySet<ToolState> = new Set([
  "input-streaming",
  "input-available",
  "approval-responded",
]);

export function formatToolName(toolName: string): string {
  return toolName.replace("tool-", "");
}
