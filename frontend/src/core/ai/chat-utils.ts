/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { Logger } from "@/utils/Logger";
import type { ChatId, ChatState } from "./state";

interface ReplaceMessagesInChatParams {
  /**
   * The state of the chats
   */
  chatState: ChatState;
  /**
   * The chat to replace the messages in
   */
  chatId: ChatId | null;
  /**
   * The messages to replace in the chat
   */
  messages: UIMessage[];
}

export const replaceMessagesInChat = ({
  chatState,
  chatId,
  messages,
}: ReplaceMessagesInChatParams): ChatState => {
  if (!chatId) {
    Logger.warn("No active chat");
    return chatState;
  }
  const chat = chatState.chats.get(chatId);
  if (!chat) {
    Logger.warn("No active chat");
    return chatState;
  }

  // Create copy of chats to modify
  const newChats = new Map(chatState.chats);
  const timestamp = Date.now();

  newChats.set(chat.id, {
    ...chat,
    messages: messages,
    updatedAt: timestamp,
  });

  return {
    ...chatState,
    chats: newChats,
  };
};
