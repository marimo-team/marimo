/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { atom } from "jotai";
import { willAutoContinue } from "@/components/chat/chat-utils";
import { getTurnTiming, withTurnTiming } from "@/components/chat/turn-timing";
import type { JotaiStore } from "../state/jotai";

export function createAssistantTurn(store: JotaiStore) {
  const stateAtom = atom<{ startedAt: number; ended: boolean } | null>(null);
  const start = () => {
    store.set(stateAtom, { startedAt: Date.now(), ended: false });
  };
  const reset = () => store.set(stateAtom, null);
  const stop = () => {
    store.set(stateAtom, (prev) => prev && { ...prev, ended: true });
  };
  const resume = (reply: UIMessage | undefined) => {
    const timing = reply && getTurnTiming(reply);
    const workedMs =
      timing?.finishedAt == null ? 0 : timing.finishedAt - timing.startedAt;
    store.set(stateAtom, {
      startedAt: Date.now() - workedMs,
      ended: false,
    });
  };
  const finish = (
    messages: UIMessage[],
    opts: { isAbort: boolean; isError: boolean },
  ) => {
    if (opts.isAbort || opts.isError) {
      stop();
    }
    return withTurnTiming(messages, {
      startedAt: store.get(stateAtom)?.startedAt ?? null,
      stopped: opts.isAbort,
    });
  };
  const isActive = (state: {
    isLoading: boolean;
    hasError: boolean;
    messages: UIMessage[];
  }) => {
    const turn = store.get(stateAtom);
    return (
      state.isLoading ||
      (turn != null &&
        !turn.ended &&
        !state.hasError &&
        willAutoContinue(state.messages))
    );
  };
  return { stateAtom, start, reset, stop, resume, finish, isActive };
}
