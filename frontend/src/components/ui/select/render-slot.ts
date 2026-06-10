/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";

/**
 * A customizable piece of UI: either fixed content, or a function that builds it
 * from `A`. The thunk form lets callers defer work (or read render-time args)
 * until the slot is actually shown.
 */
export type Slot<A extends unknown[] = []> =
  | React.ReactNode
  | ((...args: A) => React.ReactNode);

/** Resolve a {@link Slot} to its node, calling the thunk form with `args`. */
export function renderSlot<A extends unknown[]>(
  slot: Slot<A>,
  ...args: A
): React.ReactNode {
  return typeof slot === "function" ? slot(...args) : slot;
}
