/* Copyright 2023 Marimo. All rights reserved. */

import { CellId } from "../model/ids";
import { TypedString } from "../model/typed";

export type VariableName = TypedString<"VariableName">;

export interface Variable {
  name: VariableName;
  declaredBy: CellId[];
  usedBy: CellId[];
  /**
   * String representation of the value.
   */
  value?: string;
  /**
   * Type of the value.
   */
  dataType?: string;
}

export type Variables = Record<VariableName, Variable>;
