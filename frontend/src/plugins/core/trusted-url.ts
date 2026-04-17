/* Copyright 2026 Marimo. All rights reserved. */

import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { store } from "@/core/state/jotai";

/**
 * Whether a URL can be trusted to point at a marimo-served virtual file.
 *
 * Plugins that load remote scripts or stylesheets (e.g. MplInteractive, Panel)
 * must call this before turning a plugin-supplied URL into a `<script src>` or
 * `<link href>`. The backend normally serializes these URLs as virtual file
 * paths of the form `./@file/<byte_length>-<filename>` (see
 * `VirtualFile.create_and_register`). Accepting anything else would let a
 * maliciously crafted `<marimo-*>` element embedded in markdown load
 * attacker-controlled JavaScript at same origin, since the HTML sanitizer
 * lets arbitrary marimo custom elements and attributes through.
 *
 * Some runtimes (WASM, VS Code) have no backend to serve virtual files, so
 * `VirtualFile` falls back to inline base64 data URLs (see `virtual_file.py`).
 * We accept those only once the user has explicitly run a cell in the current
 * notebook — the same trust signal `sanitize.ts` uses to lift HTML
 * sanitization. Running a cell requires deliberate user action and already
 * executes arbitrary Python, so a data URL script loaded afterwards is not a
 * new attack surface.
 */
export function isTrustedVirtualFileUrl(url: unknown): url is string {
  if (typeof url !== "string" || url.length === 0) {
    return false;
  }
  if (/^(\.?\/)?@file\/[^?#]+$/.test(url)) {
    return true;
  }
  if (isSafeDataUrl(url) && store.get(hasRunAnyCellAtom)) {
    return true;
  }
  return false;
}

function isSafeDataUrl(url: string): boolean {
  return (
    url.startsWith("data:text/javascript;base64,") ||
    url.startsWith("data:application/javascript;base64,") ||
    url.startsWith("data:text/css;base64,")
  );
}
