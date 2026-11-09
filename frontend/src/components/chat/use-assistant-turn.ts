/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { useState } from "react";
import { createAssistantTurn } from "@/core/ai/assistant-turn";

export function useAssistantTurn() {
  const store = useStore();
  const [turn] = useState(() => createAssistantTurn(store));
  const state = useAtomValue(turn.stateAtom);
  return {
    ...turn,
    startedAt: state?.startedAt ?? null,
    hasEnded: state?.ended === true,
  };
}
