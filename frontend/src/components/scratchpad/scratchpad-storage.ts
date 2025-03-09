/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { ZodLocalStorage } from "@/utils/localStorage";

/**
 * Create a localStorage key based on the filename
 */
export const getStorageKey = (): string => {
  const filename = getFilenameFromDOM();
  return filename
    ? `marimo:scratchpad:${filename}`
    : "marimo:scratchpad:default";
};

// Schema for the scratchpad code
const scratchpadCodeSchema = z.string().default("");

/**
 * Create a ZodLocalStorage instance for the scratchpad code
 */
export const scratchpadStorage = new ZodLocalStorage<string>(
  getStorageKey(),
  scratchpadCodeSchema,
  () => "",
);

/**
 * Atom for the scratchpad code
 * Using atomWithStorage to persist the code in localStorage
 */
export const scratchpadCodeAtom = atomWithStorage<string>(getStorageKey(), "");

/**
 * Action to update the scratchpad code in localStorage
 */
export const updateScratchpadCodeAtom = atom(null, (get, set, code: string) => {
  set(scratchpadCodeAtom, code);
});
