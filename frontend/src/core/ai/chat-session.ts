/* Copyright 2026 Marimo. All rights reserved. */

import { Chat as ChatController } from "@ai-sdk/react";
import type { ChatAddToolOutputFunction, ChatInit, UIMessage } from "ai";
import { atom, createStore } from "jotai";
import { generateUUID } from "@/utils/uuid";
import { type ChatId, chatStateAtom, runningChatIdsAtom } from "./state";
export { runningChatIdsAtom } from "./state";

type ChatFinish = Parameters<NonNullable<ChatInit<UIMessage>["onFinish"]>>[0];

interface QueuedChatMessage {
  id: string;
  parts: UIMessage["parts"];
}

interface ChatSessionOptions extends Omit<ChatInit<UIMessage>, "onToolCall"> {
  id: ChatId;
  store?: ReturnType<typeof createStore>;
  saveMessages: (messages: UIMessage[]) => void;
  onRunningChange?: (isRunning: boolean) => void;
  shouldFlushQueue?: (
    finish: Pick<ChatFinish, "messages" | "isError" | "isAbort">,
  ) => boolean;
  onToolCall: (
    options: Parameters<NonNullable<ChatInit<UIMessage>["onToolCall"]>>[0] & {
      addToolOutput: ChatAddToolOutputFunction<UIMessage>;
    },
  ) => Promise<void>;
}

export function createChatSession({
  saveMessages,
  onToolCall,
  onFinish,
  onRunningChange,
  shouldFlushQueue,
  sendAutomaticallyWhen,
  store = createStore(),
  ...options
}: ChatSessionOptions) {
  const queuedMessagesAtom = atom<QueuedChatMessage[]>([]);
  const abortNoticeAtom = atom<string | null>(null);
  let stopped = false;
  let closed = false;
  let toolGeneration = 0;
  const tryFlushQueue = (
    finish: Pick<ChatFinish, "messages" | "isError" | "isAbort">,
  ) => {
    if (closed || !shouldFlushQueue?.(finish)) {
      return;
    }
    const [next, ...rest] = store.get(queuedMessagesAtom);
    if (next) {
      store.set(queuedMessagesAtom, rest);
      void sendMessage({ role: "user", parts: next.parts });
    }
  };
  const tryFlushQueueWhenReady = (generation: number) => {
    if (
      !stopped &&
      generation === toolGeneration &&
      controller.status === "ready"
    ) {
      tryFlushQueue({
        messages: controller.messages,
        isError: false,
        isAbort: false,
      });
    }
  };
  const controller = new ChatController<UIMessage>({
    ...options,
    onFinish: (finish) => {
      if (!stopped) {
        saveMessages(finish.messages);
      }
      if (!closed) {
        onFinish?.(finish);
      }
      tryFlushQueue(finish);
    },
    onToolCall: (options): Promise<void> | void => {
      if (stopped) {
        return;
      }
      const generation = toolGeneration;
      return onToolCall({
        ...options,
        addToolOutput: (output) => {
          // A tool may finish after Stop, or after another turn has started.
          if (!stopped && generation === toolGeneration) {
            return Promise.resolve(controller.addToolOutput(output)).then(() =>
              tryFlushQueueWhenReady(generation),
            );
          }
        },
      });
    },
    sendAutomaticallyWhen: (options) =>
      !stopped && (sendAutomaticallyWhen?.(options) ?? false),
  });

  // Track SDK-initiated tool turns even when the panel has no React subscription.
  const unsubscribeStatus = controller["~registerStatusCallback"](() => {
    onRunningChange?.(
      controller.status === "submitted" || controller.status === "streaming",
    );
  });

  const sendMessage: ChatController<UIMessage>["sendMessage"] = (...args) => {
    if (closed) {
      return Promise.resolve();
    }
    stopped = false;
    store.set(abortNoticeAtom, null);
    toolGeneration++;
    const request = controller.sendMessage(...args);
    saveMessages(controller.messages);
    return request;
  };

  const regenerate: ChatController<UIMessage>["regenerate"] = (...args) => {
    if (closed) {
      return Promise.resolve();
    }
    stopped = false;
    store.set(abortNoticeAtom, null);
    toolGeneration++;
    const request = controller.regenerate(...args);
    saveMessages(controller.messages);
    return request;
  };

  const stop = () => {
    stopped = true;
    toolGeneration++;
    saveMessages(controller.messages);
    return controller.stop();
  };

  const close = ({ discard = false }: { discard?: boolean } = {}) => {
    closed = true;
    store.set(markChatReadAtom, options.id);
    store.set(queuedMessagesAtom, []);
    unsubscribeStatus();
    onRunningChange?.(false);
    if (discard) {
      stopped = true;
      toolGeneration++;
      return controller.stop();
    }
    return stop();
  };

  const submitOrQueue = (parts: UIMessage["parts"]) => {
    if (closed) {
      return;
    }
    if (
      controller.status === "submitted" ||
      controller.status === "streaming" ||
      store.get(queuedMessagesAtom).length > 0
    ) {
      store.set(queuedMessagesAtom, (messages) => [
        ...messages,
        { id: generateUUID(), parts },
      ]);
    } else {
      void sendMessage({ role: "user", parts });
    }
  };

  const addToolApprovalResponse: ChatController<UIMessage>["addToolApprovalResponse"] =
    (...args) => {
      if (closed) {
        return Promise.resolve();
      }
      const generation = toolGeneration;
      return Promise.resolve(controller.addToolApprovalResponse(...args)).then(
        () => tryFlushQueueWhenReady(generation),
      );
    };

  return {
    controller,
    store,
    queuedMessagesAtom,
    abortNoticeAtom,
    sendMessage,
    regenerate,
    stop,
    close,
    submitOrQueue,
    addToolApprovalResponse,
  };
}

export type ChatSession = ReturnType<typeof createChatSession>;

// Controllers belong to the notebook's store, independent of panel visibility.
export const chatSessionsAtom = atom(() => new Map<ChatId, ChatSession>());
export const unreadChatIdsAtom = atom<ReadonlySet<ChatId>>(new Set<ChatId>());
export const viewedChatIdAtom = atom<ChatId | null>(null);
export const markChatReadAtom = atom(null, (get, set, chatId: ChatId) => {
  const unreadChatIds = get(unreadChatIdsAtom);
  if (unreadChatIds.has(chatId)) {
    const next = new Set(unreadChatIds);
    next.delete(chatId);
    set(unreadChatIdsAtom, next);
  }
});

export function deleteChats({
  store,
  chatId,
}: {
  store: ReturnType<typeof createStore>;
  chatId: ChatId | null;
}) {
  const runningChatIds = store.get(runningChatIdsAtom);
  if (chatId === null ? runningChatIds.size > 0 : runningChatIds.has(chatId)) {
    return false;
  }
  const sessions = store.get(chatSessionsAtom);
  for (const [id, session] of sessions) {
    if (chatId === null || id === chatId) {
      void session.close({ discard: true });
      sessions.delete(id);
    }
  }
  if (chatId === null) {
    store.set(unreadChatIdsAtom, new Set<ChatId>());
  } else {
    store.set(markChatReadAtom, chatId);
  }
  store.set(chatStateAtom, (prev) => {
    const chats = new Map(prev.chats);
    if (chatId === null) {
      chats.clear();
    } else {
      chats.delete(chatId);
    }
    return {
      chats,
      activeChatId:
        prev.activeChatId && chats.has(prev.activeChatId)
          ? prev.activeChatId
          : null,
      openChatIds: prev.openChatIds.filter((id) => chats.has(id)),
    };
  });
  return true;
}
