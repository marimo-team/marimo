/* Copyright 2026 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";

/**
 * The marimo compiler rewrites underscore-prefixed references inside a cell
 * (which Python would treat as module-private) into `_cell_<cell_id>_<name>`
 * so each cell gets its own private namespace. When such a reference fails at
 * runtime (`NameError: name '_cell_Hbol_a' is not defined`), the mangled name
 * leaks into the error UI. These helpers undo that mangling for display.
 *
 * Mirrors `marimo/_ast/variables.py`.
 */

// Matches `_cell_<cell_id><name>` for normal ids and UUIDs. The `[\w-]`
// id class admits hyphens; the `_\w*` name group admits the bare `_`
// local; the `(?<!_)` lookbehind skips `__marimo__cell_...` paths.
// Mirrors `_MANGLED_LOCAL_IN_TEXT_RE` in `variables.py`.
const MANGLED_LOCAL_BODY = String.raw`_cell_([^\W_][\w-]*?)(_\w*)`;
const MANGLED_LOCAL_PATTERN = String.raw`(?<!_)${MANGLED_LOCAL_BODY}`;
// Strict (whole-string) form for `unmangleLocal`; the leading `^` makes the
// lookbehind trivially satisfied, so use the bare body.
const ANCHORED_RE = new RegExp(`^${MANGLED_LOCAL_BODY}$`);
const UNANCHORED_RE = new RegExp(MANGLED_LOCAL_PATTERN);
const GLOBAL_RE = new RegExp(MANGLED_LOCAL_PATTERN, "g");

export interface UnmangledLocal {
  cellId: CellId;
  /** The original underscore-prefixed name, e.g. "_a". */
  name: string;
}

export function unmangleLocal(mangled: string): UnmangledLocal | null {
  const match = ANCHORED_RE.exec(mangled);
  if (!match) {
    return null;
  }
  return { cellId: match[1] as CellId, name: match[2] };
}

export type MangledSegment = string | UnmangledLocal;

/**
 * Split a plain text string into alternating literal text and unmangled-local
 * segments, so callers can render mixed React content.
 */
export function splitMangledLocals(text: string): MangledSegment[] {
  const segments: MangledSegment[] = [];
  GLOBAL_RE.lastIndex = 0;
  let lastIndex = 0;
  let match: RegExpExecArray | null = GLOBAL_RE.exec(text);
  while (match !== null) {
    if (match.index > lastIndex) {
      segments.push(text.slice(lastIndex, match.index));
    }
    segments.push({ cellId: match[1] as CellId, name: match[2] });
    lastIndex = match.index + match[0].length;
    match = GLOBAL_RE.exec(text);
  }
  if (lastIndex < text.length) {
    segments.push(text.slice(lastIndex));
  }
  return segments;
}

export function containsMangledLocal(text: string): boolean {
  return UNANCHORED_RE.test(text);
}
