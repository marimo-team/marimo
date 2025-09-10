/* Copyright 2025 Marimo. All rights reserved. */
import type { ContentBlock } from "@zed-industries/agent-client-protocol";
import type { groupNotifications } from "use-acp";

export type NotificationEvent = Awaited<
  ReturnType<typeof groupNotifications>
>[number][number];

// Notification events

export type ErrorNotificationEvent = Extract<
  NotificationEvent,
  { type: "error" }
>;
export type ConnectionChangeNotificationEvent = Extract<
  NotificationEvent,
  { type: "connection_change" }
>;
export type SessionNotificationEvent = Extract<
  NotificationEvent,
  { type: "session_notification" }
>;

// Session notification events

export type SessionNotificationEventData =
  SessionNotificationEvent["data"]["update"];
export type SessionNotificationEventType =
  SessionNotificationEventData["sessionUpdate"];

export type NotificationDataOf<T extends SessionNotificationEventType> =
  Extract<SessionNotificationEventData, { sessionUpdate: T }>;

// Session notification event data

export type UserNotificationEvent = NotificationDataOf<"user_message_chunk">;
export type AgentNotificationEvent = NotificationDataOf<"agent_message_chunk">;
export type AgentThoughtNotificationEvent =
  NotificationDataOf<"agent_thought_chunk">;
export type ToolCallNotificationEvent = NotificationDataOf<"tool_call">;
export type ToolCallUpdateNotificationEvent =
  NotificationDataOf<"tool_call_update">;
export type PlanNotificationEvent = NotificationDataOf<"plan">;

export type ContentBlockType = ContentBlock["type"];
export type ContentBlockOf<T extends ContentBlockType> = Extract<
  ContentBlock,
  { type: T }
>;
