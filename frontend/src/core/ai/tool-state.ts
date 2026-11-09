/* Copyright 2026 Marimo. All rights reserved. */

import {
  isToolUIPart,
  lastAssistantMessageIsCompleteWithApprovalResponses,
  lastAssistantMessageIsCompleteWithToolCalls,
  type ToolUIPart,
  type UIMessage,
} from "ai";

/**
 * Auto-send the next turn when the last assistant message ends with a
 * tool call ready to round-trip. Any non-tool trailing part (text, file,
 * source-*, reasoning, data-*, new step-start) means the assistant has
 * already answered, so we leave the next turn to the user. State checks
 * are delegated to the SDK to stay in sync with upstream.
 */
export function hasPendingToolCalls(messages: UIMessage[]): boolean {
  const lastMessage = messages.at(-1);
  if (!lastMessage || lastMessage.role !== "assistant") {
    return false;
  }
  const lastPart = lastMessage.parts.at(-1);
  if (!lastPart || !isToolUIPart(lastPart)) {
    return false;
  }
  return (
    lastAssistantMessageIsCompleteWithToolCalls({ messages }) ||
    lastAssistantMessageIsCompleteWithApprovalResponses({ messages }) ||
    (lastPart.state === "output-denied" && !lastPart.providerExecuted)
  );
}

export function willAutoContinue(messages: UIMessage[]): boolean {
  const lastMessage = messages.at(-1);
  const lastPart =
    lastMessage?.role === "assistant" ? lastMessage.parts.at(-1) : undefined;
  return (
    hasPendingToolCalls(messages) ||
    (lastPart != null &&
      isToolUIPart(lastPart) &&
      lastPart.state === "input-available")
  );
}

/**
 * True when the assistant is still waiting on tool execution or user approval.
 * Unlike `hasPendingToolCalls` (ready to auto-resume), these states must block
 * releasing queued user messages.
 */
export function hasUnresolvedToolCalls(messages: UIMessage[]): boolean {
  const lastMessage = messages.at(-1);
  if (!lastMessage || lastMessage.role !== "assistant") {
    return false;
  }
  return lastMessage.parts.some(
    (part) => isToolUIPart(part) && isUnresolvedToolState(part.state),
  );
}

function isUnresolvedToolState(state: ToolUIPart["state"]): boolean {
  switch (state) {
    case "approval-requested":
    case "input-streaming":
    case "input-available":
      return true;
    case "approval-responded":
    case "output-available":
    case "output-error":
    case "output-denied":
      return false;
    default: {
      const _exhaustive: never = state;
      return _exhaustive;
    }
  }
}

/**
 * Decide whether the message queue should release its next message after a
 * chat request settles. `onFinish` fires on every completion — including
 * aborts, errors, and each intermediate tool-call round — so the queue must
 * only advance once the assistant has genuinely finished its turn.
 */
export function shouldFlushQueue(opts: {
  isError: boolean;
  isAbort: boolean;
  hasPendingToolCalls: boolean;
  hasUnresolvedToolCalls: boolean;
}): boolean {
  if (opts.isError) {
    return false;
  }
  // User stopped the stream; release queued input even if a tool part is still
  // mid-flight (e.g. `input-streaming`).
  if (opts.isAbort) {
    return true;
  }
  return !opts.hasPendingToolCalls && !opts.hasUnresolvedToolCalls;
}
