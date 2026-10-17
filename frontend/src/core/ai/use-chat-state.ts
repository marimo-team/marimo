/* Copyright 2026 Marimo. All rights reserved. */

import type { Chat } from "@ai-sdk/react";
import type { UIMessage } from "ai";
import { useCallback, useSyncExternalStore } from "react";
import { AI_SDK_UI_THROTTLE_MS } from "./constants";

export function useChatState(controller: Chat<UIMessage>) {
  const subscribeToMessages = useCallback(
    (onChange: () => void) =>
      controller["~registerMessagesCallback"](onChange, AI_SDK_UI_THROTTLE_MS),
    [controller],
  );
  // Activity disconnects subscriptions while hidden. Read the controller directly
  // so reopening cannot reuse a message snapshot from before it was hidden.
  const getMessages = useCallback(() => controller.messages, [controller]);
  const messages = useSyncExternalStore(
    subscribeToMessages,
    getMessages,
    getMessages,
  );
  const status = useSyncExternalStore(
    controller["~registerStatusCallback"],
    () => controller.status,
    () => controller.status,
  );
  const error = useSyncExternalStore(
    controller["~registerErrorCallback"],
    () => controller.error,
    () => controller.error,
  );
  return { messages, status, error };
}
