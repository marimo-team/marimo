/* Copyright 2024 Marimo. All rights reserved. */

import type { Message as AIMessage } from "@ai-sdk/react";
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { adaptForLocalStorage } from "@/utils/storage";
import type { TypedString } from "@/utils/typed";
import type { CellId } from "../cells/ids";
import type { ChatAttachment } from "./types";

const KEY = "marimo:ai:chatState:v4";

export type ChatId = TypedString<"ChatId">;

export const aiCompletionCellAtom = atom<{
  cellId: CellId;
  initialPrompt?: string;
} | null>(null);

const INCLUDE_OTHER_CELLS_KEY = "marimo:ai:includeOtherCells";
export const includeOtherCellsAtom = atomWithStorage<boolean>(
  INCLUDE_OTHER_CELLS_KEY,
  true,
);

export interface Message {
  id: string;
  role: "user" | "assistant" | "data" | "system";
  content: string;
  timestamp: number;
  parts?: AIMessage["parts"];
  attachments?: ChatAttachment[];
}

export interface Chat {
  id: ChatId;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatState {
  chats: Map<ChatId, Chat>;
  activeChatId: ChatId | null;
}

export const chatStateAtom = atomWithStorage<ChatState>(
  KEY,
  {
    chats: new Map(),
    activeChatId: null,
  },
  adaptForLocalStorage({
    toSerializable: (value: ChatState) => ({
      chats: [...value.chats.entries()],
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
  (get, set, chatId: ChatId | null) => {
    set(chatStateAtom, (prev) => ({
      ...prev,
      activeChatId: chatId,
    }));
  },
);
