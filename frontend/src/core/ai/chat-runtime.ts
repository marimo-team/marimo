/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { hasPendingToolCalls, hasUnresolvedToolCalls } from "./tool-state";
import type { JotaiStore } from "../state/jotai";
import {
  type ChatSession,
  type ChatSessionOptions,
  createChatSession,
} from "./chat-session";
import {
  type ChatId,
  chatStateAtom,
  closeChatTab,
  runningChatIdsAtom,
  unreadChatIdsAtom,
} from "./state";

type RuntimeSessionOptions = Omit<
  ChatSessionOptions,
  "id" | "store" | "onRunningChange"
>;

function createChatRuntime(store: JotaiStore) {
  const sessions = new Map<ChatId, ChatSession>();
  let viewedChatId: ChatId | null = null;

  const markRead = (chatId: ChatId) => {
    store.set(unreadChatIdsAtom, (prev) => {
      if (!prev.has(chatId)) {
        return prev;
      }
      const next = new Set(prev);
      next.delete(chatId);
      return next;
    });
  };
  const releaseSession = (chatId: ChatId, discard: boolean) => {
    const session = sessions.get(chatId);
    if (session) {
      void session.close({ discard });
      sessions.delete(chatId);
    }
    markRead(chatId);
  };

  const setRunning = (chatId: ChatId, isRunning: boolean) => {
    if (isRunning) {
      markRead(chatId);
    }
    store.set(runningChatIdsAtom, (prev) => {
      if (prev.has(chatId) === isRunning) {
        return prev;
      }
      const next = new Set(prev);
      if (isRunning) {
        next.add(chatId);
      } else {
        next.delete(chatId);
      }
      return next;
    });
  };

  return {
    get sessions(): ReadonlyMap<ChatId, ChatSession> {
      return sessions;
    },
    get viewedChatId() {
      return viewedChatId;
    },
    getOrCreateSession(
      chatId: ChatId,
      createOptions: () => RuntimeSessionOptions,
    ): ChatSession {
      let session = sessions.get(chatId);
      if (!session) {
        session = createChatSession({
          ...createOptions(),
          id: chatId,
          store,
          onRunningChange: (isRunning) => setRunning(chatId, isRunning),
        });
        sessions.set(chatId, session);
      }
      return session;
    },
    viewChat(chatId: ChatId) {
      viewedChatId = chatId;
      markRead(chatId);
    },
    hideChat(chatId: ChatId) {
      if (viewedChatId === chatId) {
        viewedChatId = null;
      }
    },
    finishChat({
      chatId,
      messages,
      isAbort,
      isError,
    }: {
      chatId: ChatId;
      messages: UIMessage[];
      isAbort: boolean;
      isError: boolean;
    }) {
      const session = sessions.get(chatId);
      if (
        session &&
        !isAbort &&
        !isError &&
        !hasPendingToolCalls(messages) &&
        !hasUnresolvedToolCalls(messages) &&
        store.get(session.stateAtom).queuedMessages.length === 0 &&
        viewedChatId !== chatId &&
        store.get(chatStateAtom).chats.has(chatId)
      ) {
        store.set(unreadChatIdsAtom, (prev) =>
          prev.has(chatId) ? prev : new Set(prev).add(chatId),
        );
      }
    },
    pruneDrafts(currentChatId: ChatId) {
      const { chats } = store.get(chatStateAtom);
      for (const [id, session] of sessions) {
        if (id !== currentChatId && !chats.has(id) && !session.isActive()) {
          releaseSession(id, true);
        }
      }
    },
    closeTab(chatId: ChatId) {
      releaseSession(chatId, false);
      store.set(chatStateAtom, (prev) => closeChatTab(prev, chatId));
    },
    deleteChats(chatId: ChatId | null): boolean {
      const running = store.get(runningChatIdsAtom);
      if (chatId === null ? running.size > 0 : running.has(chatId)) {
        return false;
      }
      for (const id of sessions.keys()) {
        if (chatId === null || id === chatId) {
          releaseSession(id, true);
        }
      }
      if (chatId === null) {
        store.set(unreadChatIdsAtom, new Set<ChatId>());
      } else {
        markRead(chatId);
      }
      store.set(chatStateAtom, (prev) => {
        const nextState = chatId === null ? prev : closeChatTab(prev, chatId);
        const chats = new Map(prev.chats);
        if (chatId === null) {
          chats.clear();
        } else {
          chats.delete(chatId);
        }
        return {
          chats,
          activeChatId:
            nextState.activeChatId && chats.has(nextState.activeChatId)
              ? nextState.activeChatId
              : null,
          openChatIds: nextState.openChatIds.filter((id) => chats.has(id)),
        };
      });
      return true;
    },
  };
}

export type ChatRuntime = ReturnType<typeof createChatRuntime>;
const runtimes = new WeakMap<JotaiStore, ChatRuntime>();

export function getChatRuntime(store: JotaiStore): ChatRuntime {
  let runtime = runtimes.get(store);
  if (!runtime) {
    runtime = createChatRuntime(store);
    runtimes.set(store, runtime);
  }
  return runtime;
}
