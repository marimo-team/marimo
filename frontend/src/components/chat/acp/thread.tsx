/* Copyright 2025 Marimo. All rights reserved. */
import React from "react";
import { groupNotifications } from "use-acp";
import {
  ConnectionChangeBlock,
  ErrorBlock,
  SessionNotificationsBlock,
} from "./blocks";

type NotificationEvent = Awaited<
  ReturnType<typeof groupNotifications>
>[number][number];

interface AgentThreadProps {
  notifications: NotificationEvent[];
  isConnected: boolean;
  onRetryConnection?: () => void;
  onRetryLastAction?: () => void;
  onDismissError?: (errorId: string) => void;
}

export const AgentThread = ({
  notifications,
  isConnected,
  onRetryConnection,
  onRetryLastAction,
  onDismissError,
}: AgentThreadProps) => {
  const combinedNotifications = groupNotifications(notifications);

  const renderNotification = (group: NotificationEvent[]) => {
    if (group.length === 0) {
      return null;
    }

    if (isErrorGroup(group)) {
      const firstError = group[0];
      return (
        <ErrorBlock
          key={firstError.id}
          data={firstError.data}
          onRetry={onRetryLastAction}
          onDismiss={
            onDismissError ? () => onDismissError(firstError.id) : undefined
          }
        />
      );
    }
    if (isConnectionChangeGroup(group)) {
      const firstConnectionChange = group[0];
      return (
        <ConnectionChangeBlock
          key={firstConnectionChange.id}
          data={firstConnectionChange.data}
          isConnected={isConnected}
          onRetry={onRetryConnection}
          timestamp={firstConnectionChange.timestamp}
        />
      );
    }
    if (isSessionNotificationGroup(group)) {
      const startTimestamp = group[0].timestamp;
      const endTimestamp = group[group.length - 1].timestamp;
      const data = group.map((item) => item.data.update);
      return (
        <SessionNotificationsBlock
          data={data}
          startTimestamp={startTimestamp}
          endTimestamp={endTimestamp}
        />
      );
    }
    return "Unknown notification type";
  };

  return (
    <div className="flex flex-col gap-4 px-2 pb-10">
      {combinedNotifications.map((notification) => (
        <React.Fragment key={notification[0].id}>
          {renderNotification(notification)}
        </React.Fragment>
      ))}
    </div>
  );
};

function isErrorGroup(
  group: NotificationEvent[],
): group is Extract<NotificationEvent, { type: "error" }>[] {
  // We only check the first since we know the group is the same type
  return group[0].type === "error";
}

function isConnectionChangeGroup(
  group: NotificationEvent[],
): group is Extract<NotificationEvent, { type: "connection_change" }>[] {
  // We only check the first since we know the group is the same type
  return group[0].type === "connection_change";
}

function isSessionNotificationGroup(
  group: NotificationEvent[],
): group is Extract<NotificationEvent, { type: "session_notification" }>[] {
  // We only check the first since we know the group is the same type
  return group[0].type === "session_notification";
}
