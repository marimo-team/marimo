/* Copyright 2026 Marimo. All rights reserved. */

import { Chat as ChatController } from "@ai-sdk/react";
import type {
  ChatAddToolOutputFunction,
  ChatInit,
  ChatOnFinishCallback,
  ChatOnToolCallCallback,
  UIMessage,
} from "ai";
import { type Atom, atom, createStore } from "jotai";
import type { JotaiStore } from "../state/jotai";
import { generateUUID } from "@/utils/uuid";
import {
  type AssistantTurn,
  finishAssistantTurn,
  isAssistantTurnActive,
  resumeAssistantTurn,
} from "./assistant-turn";
import type { ChatId } from "./state";

type ChatFinish = Parameters<ChatOnFinishCallback<UIMessage>>[0];
type ChatCompletion = Pick<ChatFinish, "messages" | "isError" | "isAbort">;

export interface QueuedChatMessage {
  id: string;
  parts: UIMessage["parts"];
}

export interface ChatSessionState {
  readonly queuedMessages: readonly QueuedChatMessage[];
  readonly abortNotice: string | null;
  readonly turn: AssistantTurn | null;
}

export interface ChatSessionOptions extends Pick<
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
  const stateAtom = atom<ChatSessionState>({
    queuedMessages: [],
    abortNotice: null,
    turn: null,
  });
  const updateState = (patch: Partial<ChatSessionState>) => {
    store.set(stateAtom, (prev) => ({ ...prev, ...patch }));
  };
  const finishTurn = (
    messages: UIMessage[],
    finish: Pick<ChatCompletion, "isAbort" | "isError">,
  ) => {
    const result = finishAssistantTurn({
      turn: store.get(stateAtom).turn,
      messages,
      ...finish,
    });
    updateState({ turn: result.turn });
    return result.messages;
  };
  let stopped = false;
  let closed = false;
  let toolGeneration = 0;
  const tryFlushQueue = (finish: ChatCompletion) => {
    if (closed || !shouldFlushQueue?.(finish)) {
      return;
    }
    const [next, ...rest] = store.get(stateAtom).queuedMessages;
    if (next) {
      updateState({ queuedMessages: rest });
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
        controller.messages = finishTurn(finish.messages, finish);
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
      !store.get(stateAtom).turn?.ended &&
      (sendAutomaticallyWhen?.(options) ?? false),
  });

  const isLoading = () =>
    controller.status === "submitted" || controller.status === "streaming";
  const isActive = () =>
    isAssistantTurnActive({
      turn: store.get(stateAtom).turn,
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

  const beginTurn = () => {
    stopped = false;
    updateState({
      abortNotice: null,
      turn: { startedAt: Date.now(), ended: false },
    });
    toolGeneration++;
  };

  const sendMessage: ChatController<UIMessage>["sendMessage"] = (...args) => {
    if (closed) {
      return Promise.resolve();
    }
    beginTurn();
    const request = controller.sendMessage(...args);
    saveMessages(controller.messages);
    return request;
  };

  const regenerate: ChatController<UIMessage>["regenerate"] = (...args) => {
    if (closed) {
      return Promise.resolve();
    }
    beginTurn();
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
      controller.messages = finishTurn(controller.messages, {
        isAbort: true,
        isError: false,
      });
    }
    saveMessages(controller.messages);
    const request = controller.stop();
    if (wasLoading) {
      return request;
    }
    tryFlushQueue({
      messages: controller.messages,
      isAbort: true,
      isError: false,
    });
    return request;
  };

  const close = ({ discard = false }: { discard?: boolean } = {}) => {
    closed = true;
    updateState({ queuedMessages: [] });
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
    if (isActive() || store.get(stateAtom).queuedMessages.length > 0) {
      updateState({
        queuedMessages: [
          ...store.get(stateAtom).queuedMessages,
          { id: generateUUID(), parts },
        ],
      });
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
      updateState({ turn: resumeAssistantTurn(controller.messages.at(-1)) });
      const generation = toolGeneration;
      return Promise.resolve(controller.addToolApprovalResponse(...args)).then(
        () => tryFlushQueueWhenReady(generation),
      );
    };

  const readableState: Atom<ChatSessionState> = stateAtom;
  return {
    controller,
    store,
    stateAtom: readableState,
    setAbortNotice: (abortNotice: string | null) =>
      updateState({ abortNotice }),
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
