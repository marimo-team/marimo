/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import type { FileUIPart } from "ai";
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { toast } from "@/components/ui/use-toast";
import { uniqueBy } from "@/utils/arrays";
import { Logger } from "@/utils/Logger";
import { adaptForLocalStorage, jotaiJsonStorage } from "@/utils/storage/jotai";
import type { TypedString } from "@/utils/typed";
import type { CellId } from "../cells/ids";
import type { ChatOptions } from "../network/types";

const KEY = "marimo:ai:chatState:v5";
export const MAX_STORED_CHATS = 25;

export type ChatId = TypedString<"ChatId">;

export interface AiCompletionCell {
  cellId: CellId;
  initialPrompt?: string;
  triggerImmediately?: boolean;
}

export const aiCompletionCellAtom = atom<AiCompletionCell | null>(null);

/**
 * A prompt queued to be delivered to the AI assistant panel.
 * The active panel consumes this on mount/when ready, then clears it.
 */
export interface PendingAiPrompt {
  prompt: string;
  submit: boolean;
  append?: boolean;
}

export const pendingAiPromptAtom = atom<PendingAiPrompt | null>(null);

export const runningChatIdsAtom = atom<ReadonlySet<ChatId>>(new Set<ChatId>());
export const chatGenerationInProgressAtom = atom(
  (get) => get(runningChatIdsAtom).size > 0,
);

const CHAT_OPTIONS_KEY = "marimo:ai:chatOptions";
export const chatOptionsAtom = atomWithStorage<Required<ChatOptions>>(
  CHAT_OPTIONS_KEY,
  {
    webSearch: false,
  },
  jotaiJsonStorage,
);

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
  /** Chat ids with an open tab, in left-to-right order. */
  openChatIds: ChatId[];
}

function removeEmptyChats(chatState: Map<ChatId, Chat>): Map<ChatId, Chat> {
  const result = new Map<ChatId, Chat>();

  for (const [chatId, chat] of chatState.entries()) {
    if (chat.messages.length === 0) {
      continue;
    }
    const dedupedMessages = uniqueBy(chat.messages, (message) => message.id);
    result.set(chatId, { ...chat, messages: dedupedMessages });
  }
  return result;
}

interface SerializableChatState {
  chats: [ChatId, Chat][];
  activeChatId: ChatId | null;
  openChatIds?: ChatId[];
}

function sanitizeOpenChatIds(
  chats: Map<ChatId, Chat>,
  openChatIds: ChatId[],
): ChatId[] {
  return [...new Set(openChatIds)].filter((id) => chats.has(id));
}

/**
 * Keep the most recently updated chats, plus any chat in
 * `protectedIds` (i.e. with an open tab) regardless of age.
 */
export function pruneChats(
  chats: Map<ChatId, Chat>,
  protectedIds: Iterable<ChatId>,
): Map<ChatId, Chat> {
  if (chats.size <= MAX_STORED_CHATS) {
    return chats;
  }
  const protectedSet = new Set(protectedIds);
  const byRecency = [...chats.values()].toSorted(
    (a, b) => b.updatedAt - a.updatedAt,
  );
  const kept = new Map<ChatId, Chat>();
  for (const chat of byRecency) {
    if (kept.size < MAX_STORED_CHATS || protectedSet.has(chat.id)) {
      kept.set(chat.id, chat);
    }
  }
  return kept;
}

export function openChatTab(chatState: ChatState, chatId: ChatId): ChatState {
  if (!chatState.chats.has(chatId)) {
    return chatState;
  }
  const openChatIds = chatState.openChatIds.includes(chatId)
    ? chatState.openChatIds
    : [...chatState.openChatIds, chatId];
  return {
    ...chatState,
    openChatIds,
    activeChatId: chatId,
  };
}

export function closeChatTab(chatState: ChatState, chatId: ChatId): ChatState {
  const closedIndex = chatState.openChatIds.indexOf(chatId);
  if (closedIndex === -1) {
    return chatState;
  }

  const openChatIds = chatState.openChatIds.filter((id) => id !== chatId);

  const activeChatId =
    chatState.activeChatId === chatId
      ? (openChatIds[Math.min(closedIndex, openChatIds.length - 1)] ?? null)
      : chatState.activeChatId;

  return {
    ...chatState,
    openChatIds,
    activeChatId,
  };
}

export function addChatAndOpenTab(chatState: ChatState, chat: Chat): ChatState {
  const chats = new Map(chatState.chats);
  chats.set(chat.id, chat);
  return openChatTab({ ...chatState, chats }, chat.id);
}

const chatStorage = adaptForLocalStorage({
  toSerializable: (value: ChatState) => {
    const chats = pruneChats(removeEmptyChats(value.chats), value.openChatIds);
    return {
      chats: [...chats.entries()],
      activeChatId: value.activeChatId,
      openChatIds: sanitizeOpenChatIds(chats, value.openChatIds),
    };
  },
  fromSerializable: (value: SerializableChatState) => {
    const chats = new Map(value.chats);
    const activeChatId =
      value.activeChatId && chats.has(value.activeChatId)
        ? value.activeChatId
        : null;
    const openChatIds = sanitizeOpenChatIds(
      chats,
      value.openChatIds ?? (activeChatId ? [activeChatId] : []),
    );
    return {
      chats,
      activeChatId,
      openChatIds,
    };
  },
});

export const chatStateAtom = atomWithStorage<ChatState>(
  KEY,
  {
    chats: new Map(),
    activeChatId: null,
    openChatIds: [],
  },
  {
    ...chatStorage,
    setItem: (key, value) => {
      try {
        // Removing the key frees space even when no further writes can fit.
        if (removeEmptyChats(value.chats).size === 0) {
          chatStorage.removeItem(key);
        } else {
          chatStorage.setItem(key, value);
        }
      } catch (error) {
        Logger.warn("Could not save chat history", error);
        toast({
          id: "chat-storage-error",
          once: true,
          title: "Chat history couldn't be saved",
          description:
            "Try deleting old chats. New messages may be lost when you reload.",
          variant: "danger",
        });
      }
    },
  },
);

export const activeChatAtom = atom(
  (get) => {
    const state = get(chatStateAtom);
    if (!state.activeChatId) {
      return null;
    }
    return state.chats.get(state.activeChatId);
  },
  // oxlint-disable-next-line marimo/prefer-object-params
  (_get, set, chatId: ChatId | null) => {
    set(chatStateAtom, (prev) =>
      chatId === null
        ? { ...prev, activeChatId: null }
        : openChatTab(prev, chatId),
    );
  },
);
