/* Copyright 2024 Marimo. All rights reserved. */

import type { Message as AIMessage } from "@ai-sdk/react";
import { Logger } from "@/utils/Logger";
import type { ChatState } from "./state";

export const addMessageToChat = (
  chatState: ChatState,
  chatId: string | null,
  messageId: string,
  role: "user" | "assistant",
  content: string,
  parts?: AIMessage["parts"],
): ChatState => {
  if (!chatId) {
    Logger.warn("No active chat");
    return chatState;
  }
  // Get active chat
  const activeChat = chatState.chats.find((chat) => chat.id === chatId);
  if (!activeChat) {
    Logger.warn("No active chat");
    return chatState;
  }

  // Get message
  const message = activeChat.messages.find(
    (message) => message.id === messageId,
  );
  // Handle new message
  if (!message) {
    return {
      ...chatState,
      chats: chatState.chats.map((chat) =>
        chat.id === chatId
          ? {
              ...chat,
              messages: [
                ...chat.messages,
                {
                  id: messageId,
                  role,
                  content,
                  timestamp: Date.now(),
                  parts,
                },
              ],
              updatedAt: Date.now(),
            }
          : chat,
      ),
    };
  }
  // Handle update message
  return {
    ...chatState,
    chats: chatState.chats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: chat.messages.map((message) =>
              message.id === messageId
                ? { ...message, content, parts }
                : message,
            ),
            updatedAt: Date.now(),
          }
        : chat,
    ),
  };
};
