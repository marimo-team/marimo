/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import type { CellId } from "../cells/ids";

const KEY = "marimo:ai:chatState:v3";

export const aiCompletionCellAtom = atom<{
  cellId: CellId;
  initialPrompt?: string;
} | null>(null);

const INCLUDE_OTHER_CELLS_KEY = "marimo:ai:includeOtherCells";
export const includeOtherCellsAtom = atomWithStorage<boolean>(
  INCLUDE_OTHER_CELLS_KEY,
  true,
);

export interface Chat {
  id: string;
  title: string;
  messages: UIMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatState {
  chats: Chat[];
  activeChatId: string | null;
}

export const chatStateAtom = atomWithStorage<ChatState>(KEY, {
  chats: [],
  activeChatId: null,
});

export const activeChatAtom = atom(
  (get) => {
    const state = get(chatStateAtom);
    return state.chats.find((chat) => chat.id === state.activeChatId);
  },
  (get, set, chatId: string | null) => {
    set(chatStateAtom, (prev) => ({
      ...prev,
      activeChatId: chatId,
    }));
  },
);
