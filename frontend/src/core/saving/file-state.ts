/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { getFilenameFromDOM } from "../dom/htmlUtils";

/**
 * Atom for storing the current notebook filename.
 * This is used to scope local storage to the current notebook.
 */
export const filenameAtom = atom<string | null>(getFilenameFromDOM());

/**
 * Atom for storing the notebook's working directory (absolute path).
 * In directory mode, filenameAtom may be a relative display path;
 * this atom holds the absolute directory containing the notebook.
 */
export const cwdAtom = atom<string | null>(null);

/**
 * Set for static notebooks.
 */
export const codeAtom = atom<string | undefined>(undefined);
