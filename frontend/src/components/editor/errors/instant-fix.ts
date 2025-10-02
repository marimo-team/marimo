/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { store } from "@/core/state/jotai";

// If true, AI will immediately fix errors where possible
const BASE_KEY = "marimo:instant-ai-fix";

const instantAIFixAtom = atomWithStorage<boolean>(BASE_KEY, false);

export function useInstantAIFix() {
  const [instantAIFix, setInstantAIFix] = useAtom(instantAIFixAtom);
  return { instantAIFix, setInstantAIFix };
}

export function getInstantAIFix() {
  return store.get(instantAIFixAtom);
}
