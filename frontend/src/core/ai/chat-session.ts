/* Copyright 2026 Marimo. All rights reserved. */

import { Chat as ChatController } from "@ai-sdk/react";
import type {
  ChatAddToolOutputFunction,
  ChatInit,
  ChatOnFinishCallback,
  ChatOnToolCallCallback,
  UIMessage,
} from "ai";
import { atom, createStore } from "jotai";
import type { JotaiStore } from "../state/jotai";
import { generateUUID } from "@/utils/uuid";
import { createAssistantTurn } from "./assistant-turn";
import {
  type ChatId,
  chatStateAtom,
  closeChatTab,
  runningChatIdsAtom,
} from "./state";
export { runningChatIdsAtom } from "./state";

type ChatFinish = Parameters<ChatOnFinishCallback<UIMessage>>[0];
type ChatCompletion = Pick<ChatFinish, "messages" | "isError" | "isAbort">;

interface QueuedChatMessage {
  id: string;
  parts: UIMessage["parts"];
}

interface ChatSessionOptions extends Pick<
  ChatInit<UIMessage>,
  "messages" | "transport" | "onFinish" | "onError" | "sendAutomaticallyWhen"
> {
  id: ChatId;
  store?: JotaiStore;
  saveMessages: (messages: UIMessage[]) => void;
  onRunningChange?: (isRunning: boolean) => void;
  shouldFlushQueue?: (finish: ChatCompletion) => boolean;
  onToolCall: (
    options: Parameters<ChatOnToolCallCallback<UIMessage>>[0] & {
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
  const turn = createAssistantTurn(store);
  const turnStartedAtAtom = atom(
    (get) => get(turn.stateAtom)?.startedAt ?? null,
  );
  let stopped = false;
  let closed = false;
  let toolGeneration = 0;
  const tryFlushQueue = (finish: ChatCompletion) => {
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
        controller.messages = turn.finish(finish.messages, finish);
        saveMessages(controller.messages);
      }
      if (!closed) {
        onFinish?.({ ...finish, messages: controller.messages });
      }
      tryFlushQueue({ ...finish, messages: controller.messages });
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
      !stopped &&
      !store.get(turn.stateAtom)?.ended &&
      (sendAutomaticallyWhen?.(options) ?? false),
  });

  const isLoading = () =>
    controller.status === "submitted" || controller.status === "streaming";
  const isActive = () =>
    turn.isActive({
      isLoading: isLoading(),
      hasError: controller.error != null,
      messages: controller.messages,
    });
  let isRunning = false;
  const updateRunning = () => {
    const next = isActive();
    if (next !== isRunning) {
      isRunning = next;
      onRunningChange?.(next);
    }
  };
  // Tool turns outlive React subscriptions and can span multiple SDK requests.
  const unsubscribeStatus =
    controller["~registerStatusCallback"](updateRunning);
  const unsubscribeMessages =
    controller["~registerMessagesCallback"](updateRunning);

  const sendMessage: ChatController<UIMessage>["sendMessage"] = (...args) => {
    if (closed) {
      return Promise.resolve();
    }
    stopped = false;
    store.set(abortNoticeAtom, null);
    toolGeneration++;
    turn.start();
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
    turn.start();
    const request = controller.regenerate(...args);
    saveMessages(controller.messages);
    return request;
  };

  const stop = () => {
    const wasActive = isActive();
    stopped = true;
    toolGeneration++;
    const wasLoading = isLoading();
    if (wasActive) {
      controller.messages = turn.finish(controller.messages, {
        isAbort: true,
        isError: false,
      });
    }
    saveMessages(controller.messages);
    if (wasLoading) {
      return controller.stop();
    }
    tryFlushQueue({
      messages: controller.messages,
      isAbort: true,
      isError: false,
    });
    return Promise.resolve();
  };

  const close = ({ discard = false }: { discard?: boolean } = {}) => {
    closed = true;
    store.set(markChatReadAtom, options.id);
    store.set(queuedMessagesAtom, []);
    unsubscribeStatus();
    unsubscribeMessages();
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
    if (isActive() || store.get(queuedMessagesAtom).length > 0) {
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
      stopped = false;
      turn.resume(controller.messages.at(-1));
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
    turnStartedAtAtom,
    isActive,
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
  store: JotaiStore;
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
}
