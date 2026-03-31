/* Copyright 2026 Marimo. All rights reserved. */
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { cwdAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { PathBuilder, Paths } from "@/utils/paths";

/**
 * Get the workspace root directory (absolute path) by calculating it from the
 * current notebook's absolute directory (cwd) and its relative path from the
 * workspace root.
 */
function getWorkspaceRoot() {
  const cwd = store.get(cwdAtom);
  const filename = getFilenameFromDOM();

  if (!cwd || !filename) {
    return null;
  }

  // Split the relative path from the workspace root
  const numDirs = filename.split(/[/\\]/).filter(Boolean).length - 1;

  let root = cwd;
  for (let i = 0; i < numDirs; i++) {
    root = Paths.dirname(root);
  }
  return root;
}

export function getLSPDocument() {
  const root = getWorkspaceRoot();
  const filename = getFilenameFromDOM();

  if (root && filename) {
    return `file://${PathBuilder.guessDeliminator(root).join(root, filename)}`;
  }
  return `file://${filename ?? "/__marimo_notebook__.py"}`;
}

export function getLSPDocumentRootUri() {
  const root = getWorkspaceRoot();
  const filename = getFilenameFromDOM();

  if (root) {
    return `file://${root}`;
  }
  if (filename) {
    return `file://${Paths.dirname(filename) || "."}`;
  }
  return "file:///";
}
