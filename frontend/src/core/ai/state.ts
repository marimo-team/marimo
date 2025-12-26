/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import type { FileUIPart } from "ai";
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { uniqueBy } from "@/utils/arrays";
import { adaptForLocalStorage, jotaiJsonStorage } from "@/utils/storage/jotai";
import type { TypedString } from "@/utils/typed";
import type { CellId } from "../cells/ids";

const KEY = "marimo:ai:chatState:v5";

export type ChatId = TypedString<"ChatId">;

export interface AiCompletionCell {
  cellId: CellId;
  initialPrompt?: string;
  triggerImmediately?: boolean;
}

export const aiCompletionCellAtom = atom<AiCompletionCell | null>(null);

const INCLUDE_OTHER_CELLS_KEY = "marimo:ai:includeOtherCells";
export const includeOtherCellsAtom = atomWithStorage<boolean>(
  INCLUDE_OTHER_CELLS_KEY,
  true,
  jotaiJsonStorage,
);

export interface Message {
  id: string;
  role: "user" | "assistant" | "data" | "system";
  content: string;
  timestamp: number;
  parts?: UIMessage["parts"];
  attachments?: FileUIPart[];
}

export interface Chat {
  id: ChatId;
  title: string;
  messages: UIMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatState {
  chats: Map<ChatId, Chat>;
  activeChatId: ChatId | null;
}

function removeEmptyChats(chatState: Map<ChatId, Chat>): Map<ChatId, Chat> {
  const result = new Map<ChatId, Chat>();

  // Dedupe messages with the same id
  for (const [chatId, chat] of chatState.entries()) {
    if (chat.messages.length === 0) {
      continue;
    }
    const dedupedMessages = uniqueBy(chat.messages, (message) => message.id);
    result.set(chatId, { ...chat, messages: dedupedMessages });
  }
  return result;
}

export const chatStateAtom = atomWithStorage<ChatState>(
  KEY,
  {
    chats: new Map(),
    activeChatId: null,
  },
  adaptForLocalStorage({
    toSerializable: (value: ChatState) => ({
      chats: [...removeEmptyChats(value.chats).entries()],
      activeChatId: value.activeChatId,
    }),
    fromSerializable: (value) => ({
      chats: new Map(value.chats),
      activeChatId: value.activeChatId,
    }),
  }),
);

export const activeChatAtom = atom(
  (get) => {
    const state = get(chatStateAtom);
    if (!state.activeChatId) {
      return null;
    }
    return state.chats.get(state.activeChatId);
  },
  (_get, set, chatId: ChatId | null) => {
    set(chatStateAtom, (prev) => ({
      ...prev,
      activeChatId: chatId,
    }));
  },
);
