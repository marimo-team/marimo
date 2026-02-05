/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";

/**
 * Whether the islands have been initialized.
 *
 * false: Islands have not been initialized.
 * true: Islands have been initialized.
 * string: If there was an error initializing the islands, the string will
 *         contain the error message.
 */
export const islandsInitializedAtom = atom<boolean | string>(false);

/**
 * Whether the user has tried to interact with the islands.
 */
export const userTriedToInteractWithIslandsAtom = atom(false);

/**
 * Whether to show the islands warning indicator.
 *
 * This only happens if the user has tried to interact with the islands, but
 * they haven't been initialized yet.
 */
export const shouldShowIslandsWarningIndicatorAtom = atom((get) => {
  return (
    get(userTriedToInteractWithIslandsAtom) &&
    get(islandsInitializedAtom) === false
  );
});
