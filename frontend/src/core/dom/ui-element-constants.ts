/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Stable identifier for a UI element, deterministic across re-executions
 * of the same cell (based on cell ID + creation order).
 * Used to synchronize multiple instances and kernel state.
 */
export const OBJECT_ID_ATTR = "object-id";

/**
 * Random token that changes every time a UI element is constructed
 * (i.e., every cell execution). Used to detect stale elements and
 * force re-renders when a cell re-runs.
 */
export const RANDOM_ID_ATTR = "random-id";
