/* Copyright 2026 Marimo. All rights reserved. */

/** A single selectable item. */
export interface Option<V = string> {
  /** Selection identity; what the adapter serializes. */
  value: V;
  /** Human-readable string used for display, filtering, and chip text. */
  label: string;
  /** Whether the option can be selected. */
  disabled?: boolean;
  /** Arbitrary per-row payload (e.g. `{ count }`) read by render slots. */
  data?: unknown;
}

/**
 * Live state of an option, passed to `renderOption` so custom rows can reflect
 * selection and keyboard focus.
 */
export interface OptionState {
  /** Whether the option is currently selected. */
  checked: boolean;
  /** Whether the option is the keyboard-highlighted row. */
  active: boolean;
}

/** A select/deselect-all action scoped to the currently visible options. */
export interface BulkAction {
  label: string;
  /** False when the action is a no-op (e.g. nothing left to select). */
  enabled: boolean;
}

/** Bulk actions offered above the option list; each is omitted when N/A. */
export interface BulkActions {
  select?: BulkAction;
  deselect?: BulkAction;
}
