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
 * selection. Keyboard highlight is exposed on the row element as
 * `aria-selected` / `data-selected`, so custom rows style it via CSS.
 */
export interface OptionState {
  /** Whether the option is currently selected. */
  checked: boolean;
}

/**
 * Pure-data description of one bulk row to render above the option list. The
 * hook decides which specs exist for the current search/cap state; the facade
 * decides labels and markup.
 *
 * - `select-all` / `deselect-all` act on the whole option list — the facade
 *   already has it as a prop, so the spec just carries `enabled` for the
 *   disabled-but-visible state (e.g. everything already picked).
 * - `select-matching` / `deselect-matching` act on the search-filtered subset,
 *   which the facade can't see; `items` carries that subset so the facade can
 *   label the row ("Select N matching") and the slot is omitted when empty.
 */
export type BulkActionSpec<V> =
  | { kind: "select-all"; enabled: boolean }
  | { kind: "deselect-all"; enabled: boolean }
  | { kind: "select-matching"; items: Array<Option<V>> }
  | { kind: "deselect-matching"; items: Array<Option<V>> };

/** A renderable bulk action: spec + the closure that applies it on click. */
export type BulkAction<V> = BulkActionSpec<V> & { run: () => void };
