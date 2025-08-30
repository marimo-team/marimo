/* Copyright 2024 Marimo. All rights reserved. */

import type { Message as AIMessage } from "@ai-sdk/react";
import { Logger } from "@/utils/Logger";
import type { ChatId, ChatState } from "./state";
import type { ChatAttachment } from "./types";

interface AddMessageToChatParams {
  chatState: ChatState;
  chatId: ChatId | null;
  messageId: string;
  role: "user" | "assistant";
  content: string;
  parts?: AIMessage["parts"];
  attachments?: ChatAttachment[];
}

export const addMessageToChat = ({
  chatState,
  chatId,
  messageId,
  role,
  content,
  parts,
  attachments,
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
          content,
          timestamp: timestamp,
          parts,
          attachments,
        },
      ],
      updatedAt: timestamp,
    });
  } else {
    // Handle update message
    const newMessages = [...chat.messages];
    newMessages[messageIndex] = {
      ...newMessages[messageIndex],
      content,
      parts,
      attachments,
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
