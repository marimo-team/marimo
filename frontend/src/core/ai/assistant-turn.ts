/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { willAutoContinue } from "@/components/chat/chat-utils";
import { getTurnTiming, withTurnTiming } from "@/components/chat/turn-timing";

export interface AssistantTurn {
  readonly startedAt: number;
  readonly ended: boolean;
}

export function resumeAssistantTurn(
  reply: UIMessage | undefined,
  now = Date.now(),
): AssistantTurn {
  const timing = reply && getTurnTiming(reply);
  const workedMs =
    timing?.finishedAt == null ? 0 : timing.finishedAt - timing.startedAt;
  return { startedAt: now - workedMs, ended: false };
}

export function finishAssistantTurn({
  turn,
  messages,
  isAbort,
  isError,
}: {
  turn: AssistantTurn | null;
  messages: UIMessage[];
  isAbort: boolean;
  isError: boolean;
}) {
  return {
    turn: turn && (isAbort || isError) ? { ...turn, ended: true } : turn,
    messages: withTurnTiming(messages, {
      startedAt: turn?.startedAt ?? null,
      stopped: isAbort,
    }),
  };
}

export function isAssistantTurnActive({
  turn,
  isLoading,
  hasError,
  messages,
}: {
  turn: AssistantTurn | null;
  isLoading: boolean;
  hasError: boolean;
  messages: UIMessage[];
}): boolean {
  return (
    isLoading ||
    (turn != null && !turn.ended && !hasError && willAutoContinue(messages))
  );
}
