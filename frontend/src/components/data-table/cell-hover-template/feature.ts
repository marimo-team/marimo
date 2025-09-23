/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { InitialTableState, TableFeature } from "@tanstack/react-table";
import type { CellHoverTemplateTableState } from "./types";

export const CellHoverTemplateFeature: TableFeature = {
  getInitialState: (state?: InitialTableState): CellHoverTemplateTableState => {
    return {
      ...state,
      cellHoverTemplate: null,
    };
  },
};
