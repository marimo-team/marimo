/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Whether a URL can be trusted to point at a marimo-served virtual file.
 *
 * Plugins that load remote scripts or stylesheets (e.g. MplInteractive, Panel)
 * must call this before turning a plugin-supplied URL into a `<script src>` or
 * `<link href>`. The backend always serializes these URLs as virtual file
 * paths of the form `./@file/<byte_length>-<filename>` (see
 * `VirtualFile.create_and_register`). Accepting anything else would let a
 * maliciously crafted `<marimo-*>` element embedded in markdown load
 * attacker-controlled JavaScript at same origin, since the HTML sanitizer
 * lets arbitrary marimo custom elements and attributes through.
 */
export function isTrustedVirtualFileUrl(url: unknown): url is string {
  if (typeof url !== "string" || url.length === 0) {
    return false;
  }
  return /^(\.?\/)?@file\/[^?#]+$/.test(url);
}
