/* Copyright 2024 Marimo. All rights reserved. */
import type { NotificationDataOf, SessionNotificationEventData } from "./types";

export function isToolCalls(
  group: SessionNotificationEventData[],
): group is NotificationDataOf<"tool_call" | "tool_call_update">[] {
  // We only check the first since we know the group is the same type
  const first = group[0];
  return (
    first.sessionUpdate === "tool_call" ||
    first.sessionUpdate === "tool_call_update"
  );
}

export function isAgentThoughts(
  group: SessionNotificationEventData[],
): group is NotificationDataOf<"agent_thought_chunk">[] {
  // We only check the first since we know the group is the same type
  const first = group[0];
  return first.sessionUpdate === "agent_thought_chunk";
}

export function isUserMessages(
  group: SessionNotificationEventData[],
): group is NotificationDataOf<"user_message_chunk">[] {
  // We only check the first since we know the group is the same type
  const first = group[0];
  return first.sessionUpdate === "user_message_chunk";
}

export function isAgentMessages(
  group: SessionNotificationEventData[],
): group is NotificationDataOf<"agent_message_chunk">[] {
  // We only check the first since we know the group is the same type
  const first = group[0];
  return first.sessionUpdate === "agent_message_chunk";
}

export function isPlans(
  group: SessionNotificationEventData[],
): group is NotificationDataOf<"plan">[] {
  // We only check the first since we know the group is the same type
  const first = group[0];
  return first.sessionUpdate === "plan";
}
