/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Lets descendants of `DataTable` (column headers, etc.) ask the table to open
 * the filter pill editor for a given column. The table owns the pending
 * snapshot state and renders the editor anchored under the pills strip's
 * `+` button; consumers only fire intent via `requestAddFilter`.
 *
 * `useFilterEditor()` returns `null` outside a provider, which callers treat as
 * "filter editor not available" and hide the corresponding menu items.
 */

import { createContext, useContext } from "react";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";

export interface AddFilterRequest {
  columnId: string;
  /** Pre-select an operator (e.g. `"in"` for "Filter by values"); defaults to the column dtype's default. */
  operator?: OperatorType;
}

interface FilterEditorContextValue {
  requestAddFilter: (request: AddFilterRequest) => void;
}

const FilterEditorContext = createContext<FilterEditorContextValue | null>(
  null,
);

export const FilterEditorProvider = FilterEditorContext.Provider;

export function useFilterEditor(): FilterEditorContextValue | null {
  return useContext(FilterEditorContext);
}
