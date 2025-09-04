/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { Logger } from "@/utils/Logger";
import type { ChatId, ChatState } from "./state";

interface AddMessageToChatParams {
  chatState: ChatState;
  chatId: ChatId | null;
  messageId: string;
  role: "user" | "assistant";
  parts: UIMessage["parts"];
}

export const addMessageToChat = ({
  chatState,
  chatId,
  messageId,
  role,
  parts,
}: AddMessageToChatParams): ChatState => {
  if (!chatId) {
    Logger.warn("No active chat");
    return chatState;
  }
  const chat = chatState.chats.get(chatId);
  if (!chat) {
    Logger.warn("No active chat");
    return chatState;
  }

  const messageIndex = chat.messages.findIndex(
    (message) => message.id === messageId,
  );

  // Create copy of chats to modify
  const newChats = new Map(chatState.chats);
  const timestamp = Date.now();

  if (messageIndex === -1) {
    // Handle new message
    newChats.set(chatId, {
      ...chat,
      messages: [
        ...chat.messages,
        {
          id: messageId,
          role,
          metadata: {
            timestamp: timestamp,
          },
          parts,
        },
      ],
      updatedAt: timestamp,
    });
  } else {
    // Handle update message
    const newMessages = [...chat.messages];
    newMessages[messageIndex] = {
      ...newMessages[messageIndex],
      parts,
    };
    newChats.set(chat.id, {
      ...chat,
      messages: newMessages,
      updatedAt: timestamp,
    });
  }

  return {
    ...chatState,
    chats: newChats,
  };
};
