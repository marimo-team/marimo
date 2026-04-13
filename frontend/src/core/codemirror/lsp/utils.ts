/* Copyright 2026 Marimo. All rights reserved. */
import { lspWorkspaceAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";

export function getLspRootUri() {
  const lspWorkspace = store.get(lspWorkspaceAtom);
  // The backend provides rootUri for active notebook sessions.
  // For non-notebook pages (home, gallery), lspWorkspace is null,
  // so return a valid file URI fallback.
  return lspWorkspace?.rootUri ?? "file:///";
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
  // so return a valid file URI fallback.
  return lspWorkspace?.documentUri ?? "file:///__marimo_notebook__.py";
}
