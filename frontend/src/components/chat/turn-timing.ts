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
  const { startedAt, finishedAt, stopped } = metadata as Record<
    string,
    unknown
  >;
  if (typeof startedAt !== "number") {
    return undefined;
  }
  return {
    startedAt,
    finishedAt: typeof finishedAt === "number" ? finishedAt : undefined,
    stopped: stopped === true,
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
  const startedAt = getTurnTiming(last)?.startedAt ?? turn.startedAt;
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

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(1, Math.round(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (minutes > 0) {
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  return `${seconds}s`;
}
