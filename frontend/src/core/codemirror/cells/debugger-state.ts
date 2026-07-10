/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { CellId } from "@/core/cells/ids";
import { getRequestClient } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

/**
 * State for the experimental live debugger.
 *
 * - `debuggerCurrentLineAtom` holds the cell + line the kernel's frame watcher
 *   is currently executing (driven by `active-line` notifications). Only one
 *   cell runs at a time, so a single global value suffices.
 * - `breakpointsAtom` holds the user's gutter breakpoints, session-only. It is
 *   the source of truth; mutations are mirrored to the kernel via
 *   `sendSetBreakpoints`.
 */

export interface DebuggerLine {
  cellId: CellId;
  line: number;
}

export const debuggerCurrentLineAtom = atom<DebuggerLine | null>(null);

export const breakpointsAtom = atom<ReadonlyMap<CellId, ReadonlySet<number>>>(
  new Map<CellId, ReadonlySet<number>>(),
);

const EMPTY_LINES: ReadonlySet<number> = new Set();

/** Per-cell derived atom: the current debug line for `cellId`, or `null`. */
export function createDebuggerLineAtom(cellId: CellId) {
  return atom((get) => {
    const current = get(debuggerCurrentLineAtom);
    return current?.cellId === cellId ? current.line : null;
  });
}

/** Per-cell derived atom: the breakpoint lines for `cellId`. */
export function createCellBreakpointsAtom(cellId: CellId) {
  return atom((get) => get(breakpointsAtom).get(cellId) ?? EMPTY_LINES);
}

function sendBreakpoints(map: ReadonlyMap<CellId, ReadonlySet<number>>): void {
  const breakpoints: Record<string, number[]> = {};
  for (const [cellId, lines] of map) {
    if (lines.size > 0) {
      breakpoints[cellId] = [...lines].toSorted((a, b) => a - b);
    }
  }
  // Fire-and-forget: the request layer rethrows on failure (e.g. static or
  // wasm mode with no live kernel). Swallow it so toggling a breakpoint never
  // surfaces as an unhandled promise rejection.
  getRequestClient()
    .sendSetBreakpoints({ breakpoints })
    .catch((error) => {
      Logger.debug("Failed to sync breakpoints to kernel", { error });
    });
}

/** Remove all breakpoints for a cell and sync the full set to the kernel. */
export function clearCellBreakpoints(cellId: CellId): void {
  const prev = store.get(breakpointsAtom);
  if (!prev.has(cellId)) {
    return;
  }
  const next = new Map(prev);
  next.delete(cellId);
  store.set(breakpointsAtom, next);
  sendBreakpoints(next);
}

/** Re-push the current breakpoints to a freshly started kernel, whose `MarimoPdb` starts empty. */
export function resyncBreakpoints(): void {
  const current = store.get(breakpointsAtom);
  if (current.size > 0) {
    sendBreakpoints(current);
  }
}

/** Toggle a breakpoint at `(cellId, line)` and sync the full set to the kernel. */
export function toggleBreakpoint(cellId: CellId, line: number): void {
  const prev = store.get(breakpointsAtom);
  const next = new Map(prev);
  const lines = new Set(next.get(cellId) ?? []);
  if (lines.has(line)) {
    lines.delete(line);
  } else {
    lines.add(line);
  }
  if (lines.size > 0) {
    next.set(cellId, lines);
  } else {
    next.delete(cellId);
  }
  store.set(breakpointsAtom, next);
  sendBreakpoints(next);
}
