/* Copyright 2024 Marimo. All rights reserved. */

import { useMemo } from "react";
import { useNotebook } from "@/core/cells/cells";
import {
  extractAllVariableNames,
  generateUniqueVariableName,
} from "@/core/cells/variable-names";

/**
 * Hook to get a unique variable name generator
 *
 * @returns A function that generates unique variable names based on existing
 *          variables in the notebook
 */
export function useUniqueVariableName() {
  const notebook = useNotebook();

  // Extract all existing variable names from all cells
  const existingVariables = useMemo(() => {
    const codes = Object.values(notebook.cellData).map((cell) => cell.code);
    return extractAllVariableNames(codes);
  }, [notebook.cellData]);

  // Return a function that generates unique names
  return (baseName: string) =>
    generateUniqueVariableName(baseName, existingVariables);
}
