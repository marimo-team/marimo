/* Copyright 2024 Marimo. All rights reserved. */

import type { TypedString } from "../../utils/typed";
import type { CellId } from "../cells/ids";

export type VariableName = TypedString<"VariableName">;

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
