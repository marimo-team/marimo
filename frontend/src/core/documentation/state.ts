/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";

interface DocumentationState {
  documentation: string | null;
}

/**
 * Stores the last seen function documentation
 */
export const documentationAtom = atom<DocumentationState>({
  documentation: null,
});
