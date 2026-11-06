/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { useState } from "react";
import useEvent from "react-use-event-hook";
import { willAutoContinue } from "./chat-utils";
import { withTurnTiming } from "./turn-timing";

export function useAssistantTurn() {
  const [turn, setTurn] = useState<{
    startedAt: number;
    ended: boolean;
  } | null>(null);

  const start = useEvent(() =>
    setTurn({ startedAt: Date.now(), ended: false }),
  );
  const reset = useEvent(() => setTurn(null));

  const finish = useEvent(
    (finished: UIMessage[], opts: { isAbort: boolean; isError: boolean }) => {
      if (opts.isAbort || opts.isError) {
        setTurn((prev) => prev && { ...prev, ended: true });
      }
      return withTurnTiming(finished, turn?.startedAt ?? null);
    },
  );

  // Between requests of one turn the SDK briefly reports "ready".
  const isActive = (state: {
    isLoading: boolean;
    hasError: boolean;
    messages: UIMessage[];
  }) =>
    state.isLoading ||
    (turn != null &&
      !turn.ended &&
      !state.hasError &&
      willAutoContinue(state.messages));

  return { startedAt: turn?.startedAt ?? null, start, reset, finish, isActive };
}
