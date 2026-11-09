/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";

export interface TurnTiming {
  startedAt: number;
  finishedAt?: number;
  stopped?: boolean;
}

export function getTurnTiming(message: UIMessage): TurnTiming | undefined {
  const metadata = message.metadata;
  if (typeof metadata !== "object" || metadata === null) {
    return undefined;
  }
  if (!("startedAt" in metadata) || typeof metadata.startedAt !== "number") {
    return undefined;
  }
  const finishedAt = "finishedAt" in metadata ? metadata.finishedAt : undefined;
  return {
    startedAt: metadata.startedAt,
    finishedAt: typeof finishedAt === "number" ? finishedAt : undefined,
    stopped: "stopped" in metadata && metadata.stopped === true,
  };
}

export function withTurnTiming(
  messages: UIMessage[],
  turn: { startedAt: number | null; stopped: boolean },
  now = Date.now(),
): UIMessage[] {
  const last = messages.at(-1);
  if (last?.role !== "assistant") {
    return messages;
  }
  const startedAt = turn.startedAt ?? getTurnTiming(last)?.startedAt;
  if (startedAt == null) {
    return messages;
  }
  const metadata =
    typeof last.metadata === "object" && last.metadata !== null
      ? last.metadata
      : {};
  return [
    ...messages.slice(0, -1),
    {
      ...last,
      metadata: {
        ...metadata,
        startedAt,
        finishedAt: now,
        stopped: turn.stopped,
      },
    },
  ];
}
