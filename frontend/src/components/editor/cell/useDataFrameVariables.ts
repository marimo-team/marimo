/* Copyright 2024 Marimo. All rights reserved. */

import { useMemo } from "react";
import { useVariables } from "@/core/variables/state";
import type { Variable } from "@/core/variables/types";

export interface DataFrameVariable {
  name: string;
  value: string | null | undefined;
}

/**
 * Hook to get all DataFrame variables from the notebook
 *
 * @returns Array of DataFrame variables with their names and values
 */
export function useDataFrameVariables(): DataFrameVariable[] {
  const variables = useVariables();

  return useMemo(() => {
    const dataframes: DataFrameVariable[] = [];

    for (const [name, variable] of Object.entries(variables)) {
      if (isDataFrameVariable(variable)) {
        dataframes.push({
          name,
          value: variable.value,
        });
      }
    }

    // Sort by name for consistent ordering
    return dataframes.sort((a, b) => a.name.localeCompare(b.name));
  }, [variables]);
}

/**
 * Check if a variable is a DataFrame based on its type or value
 */
function isDataFrameVariable(variable: Variable): boolean {
  // Check dataType field
  if (variable.dataType === "DataFrame") {
    return true;
  }

  // Check value field for pandas or polars prefixes
  if (variable.value) {
    const valueLower = variable.value.toLowerCase();
    if (valueLower.startsWith("pandas:") || valueLower.startsWith("polars:")) {
      return true;
    }
  }

  return false;
}
