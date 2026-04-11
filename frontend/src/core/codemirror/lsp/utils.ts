/* Copyright 2026 Marimo. All rights reserved. */
import { lspWorkspaceAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";

export function getLspRootUri() {
  const lspWorkspace = store.get(lspWorkspaceAtom);
  // The backend provides rootUri for active notebook sessions.
  // For non-notebook pages (home, gallery), lspWorkspace is null,
  // and we safely return an empty string (LSP client won't be initialized).
  return lspWorkspace?.rootUri ?? "";
}

export function getLspWorkspaceFolders() {
  const lspWorkspace = store.get(lspWorkspaceAtom);
  const rootUri = lspWorkspace?.rootUri;
  // Return workspace folders only if rootUri is set; empty array otherwise.
  return rootUri ? [{ uri: rootUri, name: "marimo" }] : [];
}

export function getLspDocumentUri() {
  const lspWorkspace = store.get(lspWorkspaceAtom);
  // The backend provides documentUri for active notebook sessions.
  // For non-notebook pages (home, gallery), lspWorkspace is null,
  // and we safely return an empty string.
  return lspWorkspace?.documentUri ?? "";
}
