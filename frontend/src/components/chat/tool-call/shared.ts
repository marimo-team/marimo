/* Copyright 2026 Marimo. All rights reserved. */

import type { ToolUIPart } from "ai";

export type ToolState = ToolUIPart["state"];

// The AI SDK declares `approval` inline on every variant of `UIToolInvocation`
// rather than exporting a named type, so we derive ours from there.
export type ToolApproval = NonNullable<ToolUIPart["approval"]>;

export function formatToolName(toolName: string): string {
  return toolName.replace("tool-", "");
}
