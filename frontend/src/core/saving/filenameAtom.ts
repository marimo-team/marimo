/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { getFilenameFromDOM } from "../dom/htmlUtils";

// The atom is separated from the filename logic to avoid circular dependencies.
/**
 * Atom for storing the current notebook filename.
 * This is used to scope local storage to the current notebook.
 */
export const filenameAtom = atom<string | null>(getFilenameFromDOM());
