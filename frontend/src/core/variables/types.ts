/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import type { CellId } from "../cells/ids";

export type VariableName = components["schemas"]["VariableName"];

export interface Variable {
  name: VariableName;
  declaredBy: CellId[];
  usedBy: CellId[];
  /**
   * String representation of the value.
   */
  value?: string | null;
  /**
   * Type of the value.
   */
  dataType?: string | null;
}

export type Variables = Record<VariableName, Variable>;
