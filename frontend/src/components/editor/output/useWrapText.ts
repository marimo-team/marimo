/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";

const WRAP_TEXT_KEY = "marimo:console:wrapText";

// Atom for storing wrap text preference - shared across all console outputs
const wrapTextAtom = atomWithStorage<boolean>(WRAP_TEXT_KEY, false);

export function useWrapText() {
  const [wrapText, setWrapText] = useAtom(wrapTextAtom);
  return { wrapText, setWrapText };
}
