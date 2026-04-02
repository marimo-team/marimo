/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithStorage } from "jotai/utils";

/**
 * Whether pressing Enter accepts an autocomplete suggestion.
 * Stored in localStorage — frontend-only, never sent to backend.
 * Default true = Enter accepts (same as original behavior).
 */
export const acceptSuggestionOnEnterAtom = atomWithStorage<boolean>(
  "marimo:acceptSuggestionOnEnter",
  true,
);
