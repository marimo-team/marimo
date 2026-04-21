/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { autoInstantiateAtom } from "@/core/config/config";
import { getInitialAppMode } from "@/core/mode";
import { store } from "@/core/state/jotai";

/**
 * Whether the current notebook already has an established trust signal,
 * i.e. a context in which a markdown cell is already allowed to run
 * arbitrary inline HTML/JS.
 *
 * This mirrors the disable-sanitization condition in `sanitize.ts`. When
 * sanitization is off, an attacker-controlled markdown cell could embed a
 * raw `<script>` tag directly, so refusing plugin-supplied `data:` URLs at
 * this layer adds no extra protection — it only prevents legitimate widgets
 * from loading.
 *
 * Trust is established by any of:
 * - `hasRunAnyCell`: user explicitly clicked "run" at least once.
 * - `autoInstantiate`: notebook is configured to run on open.
 * - read-mode (`marimo run`, static HTML, islands served as apps): the
 *   notebook is intrinsically an execution context.
 *
 * Keep this condition in sync with `sanitize.ts`.
 */
const notebookTrustEstablishedAtom = atom<boolean>((get) => {
  if (get(hasRunAnyCellAtom)) {
    return true;
  }
  if (get(autoInstantiateAtom)) {
    return true;
  }
  try {
    return getInitialAppMode() === "read";
  } catch {
    // Mode not initialized yet — be conservative and treat as untrusted.
    return false;
  }
});

/**
 * Whether a URL can be trusted to point at a marimo-served virtual file.
 *
 * Plugins that load remote scripts or stylesheets (e.g. MplInteractive,
 * Panel, anywidget) must call this before turning a plugin-supplied URL
 * into a `<script src>` or `<link href>`. The backend normally serializes
 * these URLs as virtual file paths of the form
 * `./@file/<byte_length>-<filename>` (see `VirtualFile.create_and_register`).
 * Accepting arbitrary URLs would let a maliciously crafted `<marimo-*>`
 * element embedded in markdown load attacker-controlled JavaScript at
 * same origin, since the HTML sanitizer lets arbitrary `marimo-*` custom
 * elements and attributes through.
 *
 * Runtime compatibility:
 * - **Server / editor / VS Code extension**: backend has
 *   `virtual_files_supported=True`, so URLs are `./@file/...` and match
 *   the first branch below.
 * - **Islands / static HTML export**: URLs in the serialized notebook are
 *   still `./@file/...` — the frontend's fetch patch and
 *   `resolveVirtualFileURL` swap them for inline data URLs at load time.
 *   Plugins see the `./@file/...` form, so the first branch accepts them.
 * - **WASM / Pyodide (`marimo-lite`)**: the kernel context sets
 *   `virtual_files_supported=False` (see `pyodide_session.py`) and
 *   `VirtualFile` emits a base64 data URL directly. Panel's
 *   `extensionUrl`, anywidget's `jsUrl`, and mpl-interactive's script/CSS
 *   all arrive as `data:` URLs in this mode. The second branch accepts
 *   them once notebook trust is established — which, in WASM run-mode or
 *   when `auto_instantiate` is on, happens automatically (cells auto-run
 *   on load and sanitization is already disabled).
 */
export function isTrustedVirtualFileUrl(url: unknown): url is string {
  if (typeof url !== "string" || url.length === 0) {
    return false;
  }
  // Canonical virtual-file path. Used by server-backed modes (including
  // VS Code) and static exports (islands, `marimo export html`).
  if (/^(\.?\/)?@file\/[^?#]+$/.test(url)) {
    return true;
  }
  // Inline base64 data URL. Used by serverless runtimes (WASM / Pyodide)
  // where `virtual_files_supported=False`. Only trust once the notebook
  // itself is trusted — in those contexts a malicious markdown cell could
  // embed raw `<script>` tags anyway, so this adds no new attack surface.
  if (isSafeDataUrl(url) && store.get(notebookTrustEstablishedAtom)) {
    return true;
  }
  return false;
}

/**
 * Safe data URL formats: JS/CSS inlined as base64. Non-base64 data URLs
 * and other MIME types (HTML, SVG, octet-stream, etc.) are refused
 * because their payload is not length-delimited by base64 and can carry
 * unescaped attacker content.
 */
function isSafeDataUrl(url: string): boolean {
  return (
    url.startsWith("data:text/javascript;base64,") ||
    url.startsWith("data:application/javascript;base64,") ||
    url.startsWith("data:text/css;base64,")
  );
}
