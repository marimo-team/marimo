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

// Matches `_cell_<cell_id><name>` where the cell id has no underscores and
// `<name>` begins with `_` (the original ref was a local underscore name).
// Python mangle is `f"_cell_{cell_id}{ref}"` (variables.py:41), so the only
// `_` between the id and the name is the leading `_` of the name itself.
// Non-greedy id group + name group that must start with `_` correctly
// recovers the boundary.
//
// Anchored on a single leading `_cell_`, so the compiled cell file path
// `__marimo__cell_<id>_.py` (two leading underscores, no trailing `_<name>`)
// does not match.
const MANGLED_LOCAL_PATTERN = String.raw`_cell_([^\W_]\w*?)(_\w+)`;
const ANCHORED_RE = new RegExp(`^${MANGLED_LOCAL_PATTERN}$`);
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
