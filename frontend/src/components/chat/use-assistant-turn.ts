/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { useState } from "react";
import useEvent from "react-use-event-hook";
import { willAutoContinue } from "./chat-utils";
import { getTurnTiming, withTurnTiming } from "./turn-timing";

export function useAssistantTurn() {
  const [turn, setTurn] = useState<{
    startedAt: number;
    ended: boolean;
  } | null>(null);

  const start = useEvent(() =>
    setTurn({ startedAt: Date.now(), ended: false }),
  );
  const reset = useEvent(() => setTurn(null));
  const stop = useEvent(() =>
    setTurn((prev) => prev && { ...prev, ended: true }),
  );

  // Shift the start forward so time spent waiting on the user isn't counted.
  const resume = useEvent((reply: UIMessage | undefined) => {
    const timing = reply && getTurnTiming(reply);
    const workedMs =
      timing?.finishedAt == null ? 0 : timing.finishedAt - timing.startedAt;
    setTurn({ startedAt: Date.now() - workedMs, ended: false });
  });

  const finish = useEvent(
    (finished: UIMessage[], opts: { isAbort: boolean; isError: boolean }) => {
      if (opts.isAbort || opts.isError) {
        stop();
      }
      return withTurnTiming(finished, {
        startedAt: turn?.startedAt ?? null,
        stopped: opts.isAbort,
      });
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

  return {
    startedAt: turn?.startedAt ?? null,
    hasEnded: turn?.ended === true,
    start,
    resume,
    stop,
    reset,
    finish,
    isActive,
  };
}
