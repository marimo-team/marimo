/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import { RequestingTree } from "./requesting-tree";

// State lives outside of the component
// to preserve the state when the component is unmounted
export const treeAtom = atom<RequestingTree>((get) => {
  const client = get(requestClientAtom);
  invariant(client, "no requestClientAtom set");
  return new RequestingTree({
    listFiles: client.sendListFiles,
    createFileOrFolder: client.sendCreateFileOrFolder,
    deleteFileOrFolder: client.sendDeleteFileOrFolder,
    renameFileOrFolder: client.sendRenameFileOrFolder,
  });
});

export const openStateAtom = atom<Record<string, boolean>>({});

export async function refreshRoot() {
  await store.get(treeAtom).refreshAll([]);
}
