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
  const activeChatIndex = chatState.chats.findIndex(
    (chat) => chat.id === chatId,
  );
  if (activeChatIndex === -1) {
    Logger.warn("No active chat");
    return chatState;
  }

  const chat = chatState.chats[activeChatIndex];
  const messageIndex = chat.messages.findIndex(
    (message) => message.id === messageId,
  );

  // Create copy of chats to modify
  const newChats = [...chatState.chats];
  const CURRENT_TIMESTAMP = Date.now();

  if (messageIndex === -1) {
    // Handle new message
    newChats[activeChatIndex] = {
      ...chat,
      messages: [
        ...chat.messages,
        {
          id: messageId,
          role,
          content,
          timestamp: CURRENT_TIMESTAMP,
          parts,
        },
      ],
      updatedAt: CURRENT_TIMESTAMP,
    };
  } else {
    // Handle update message
    const newMessages = [...chat.messages];
    newMessages[messageIndex] = {
      ...newMessages[messageIndex],
      content,
      parts,
    };
    newChats[activeChatIndex] = {
      ...chat,
      messages: newMessages,
      updatedAt: CURRENT_TIMESTAMP,
    };
  }

  return {
    ...chatState,
    chats: newChats,
  };
};
