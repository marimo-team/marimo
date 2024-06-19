/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtom } from "jotai";
import { getFilenameFromDOM } from "../dom/htmlUtils";

const filenameAtom = atom<string | null>(getFilenameFromDOM());

const filetitleAtom = atom((get) => {
  const filename = get(filenameAtom);
  return filename ? filename.split("/").pop() : null;
});

export function useFilename() {
  return useAtom(filenameAtom);
}

export function useFiletitle() {
  return useAtom(filetitleAtom);
}
