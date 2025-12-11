/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

const MAX_HISTORY_ITEMS = 15;
const KEY = "marimo:scratchpadHistory:v1";

// Atom for storing the history
export const scratchpadHistoryAtom = atomWithStorage<string[]>(
  KEY,
  [],
  jotaiJsonStorage,
);

// Atom for controlling the visibility of the history list
export const historyVisibleAtom = atom(false);

// Action to add a new item to history
export const addToHistoryAtom = atom(null, (get, set, newItem: string) => {
  // Trim whitespace
  newItem = newItem.trim();
  // Skip empty
  if (!newItem) {
    return;
  }
  const history = get(scratchpadHistoryAtom);
  const updatedHistory = [
    newItem,
    ...history.filter((item) => item !== newItem),
  ].slice(0, MAX_HISTORY_ITEMS);
  set(scratchpadHistoryAtom, updatedHistory);
});
