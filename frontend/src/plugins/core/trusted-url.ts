/* Copyright 2026 Marimo. All rights reserved. */

import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { hasTrustedExportContext } from "@/core/static/export-context";
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
 * Some runtimes (WASM, VS Code, and trusted exported notebook contexts such as
 * Quarto islands) have no backend to serve virtual files, so `VirtualFile`
 * falls back to inline base64 data URLs (see `virtual_file.py`).
 * We accept those only once the user has explicitly run a cell in the current
 * notebook, or when a first-party export script has installed a trusted
 * notebook export context. Both cases already imply trust in notebook-authored
 * code, so loading the matching data URL is not a new attack surface.
 */
export function isTrustedVirtualFileUrl(url: unknown): url is string {
  if (typeof url !== "string" || url.length === 0) {
    return false;
  }
  if (/^(\.?\/)?@file\/[^?#]+$/.test(url)) {
    return true;
  }
  if (isSafeDataUrl(url)) {
    return true;
  }
  return false;
}

/**
 * Intentionally narrower than `hasTrustedNotebookContext` in
 * `@/core/static/export-context`: `auto_instantiate` and `read` mode are
 * deliberately excluded here. Both can be triggered by DOM-observable page
 * shape, and accepting inline base64 `data:` JS/CSS payloads on their
 * strength would let a hostile notebook page smuggle attacker-controlled
 * script into the same origin. Keep this gate tied only to "user actively
 * ran a cell" or "first-party exporter installed a trusted runtime marker".
 */
function hasNotebookTrustedDataUrlContext(): boolean {
  return store.get(hasRunAnyCellAtom) || hasTrustedExportContext();
}

/**
 * Safe data URL formats: JS/CSS inlined as base64. Non-base64 data URLs and
 * other MIME types (HTML, SVG, octet-stream, etc.) are refused because they
 * broaden the surface for attacker-controlled inline content.
 */
function isSafeDataUrl(url: string): boolean {
  const isSafeKind =
    url.startsWith("data:text/javascript;base64,") ||
    url.startsWith("data:application/javascript;base64,") ||
    url.startsWith("data:text/css;base64,");
  if (!isSafeKind) {
    return false;
  }
  return hasNotebookTrustedDataUrlContext();
}
