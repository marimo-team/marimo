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
  let combinedNotifications = groupNotifications(notifications);

  // Filter out all connection changes unless it is the last one
  combinedNotifications = combinedNotifications.filter((group, index) => {
    const isLast = index === combinedNotifications.length - 1;
    if (isLast) {
      return true;
    }
    if (isConnectionChangeGroup(group)) {
      return false;
    }
    return true;
  });

  const renderNotification = (group: NotificationEvent[]) => {
    if (group.length === 0) {
      return null;
    }

    if (isErrorGroup(group)) {
      const lastError = group[group.length - 1];
      return (
        <ErrorBlock
          key={lastError.id}
          data={lastError.data}
          onRetry={onRetryLastAction}
          onDismiss={
            onDismissError ? () => onDismissError(lastError.id) : undefined
          }
        />
      );
    }
    if (isConnectionChangeGroup(group)) {
      const lastConnectionChange = group[group.length - 1];
      return (
        <ConnectionChangeBlock
          key={lastConnectionChange.id}
          data={lastConnectionChange.data}
          isConnected={isConnected}
          onRetry={onRetryConnection}
          timestamp={lastConnectionChange.timestamp}
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
