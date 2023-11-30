/* Copyright 2023 Marimo. All rights reserved. */

import { atom, useAtom } from "jotai";
import { getFilenameFromDOM } from "../dom/htmlUtils";

const filenameAtom = atom<string | null>(getFilenameFromDOM());

export function useFilename() {
  return useAtom(filenameAtom);
}
