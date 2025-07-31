/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import {
  sendCreateFileOrFolder,
  sendDeleteFileOrFolder,
  sendListFiles,
  sendRenameFileOrFolder,
} from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { RequestingTree } from "./requesting-tree";

// State lives outside of the component
// to preserve the state when the component is unmounted
export const treeAtom = atom<RequestingTree>(
  new RequestingTree({
    listFiles: sendListFiles,
    createFileOrFolder: sendCreateFileOrFolder,
    deleteFileOrFolder: sendDeleteFileOrFolder,
    renameFileOrFolder: sendRenameFileOrFolder,
  }),
);
export const openStateAtom = atom<Record<string, boolean>>({});

export async function refreshRoot() {
  await store.get(treeAtom).refreshAll([]);
}
