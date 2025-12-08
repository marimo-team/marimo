/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Utility functions for working with variable names in notebook cells
 */

/**
 * Simple regex to extract Python assignment targets from the left-hand side of assignments.
 * This is a simplified approach - it won't handle all Python syntax but covers common cases.
 *
 * Matches patterns like:
 * - x = ...
 * - x, y = ...
 * - x: int = ...
 */
function extractVariableNamesFromCode(code: string): Set<string> {
  const variables = new Set<string>();

  // Match assignment statements (simple pattern)
  // This regex looks for variable names at the start of lines or after commas
  // followed by = or : (for type annotations)
  const assignmentPattern = /^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::|=)/gm;

  let match;
  while ((match = assignmentPattern.exec(code)) !== null) {
    variables.add(match[2]);
  }

  // Also handle tuple unpacking: x, y, z = ...
  const tuplePattern =
    /^(\s*)([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)+)\s*=/gm;
  while ((match = tuplePattern.exec(code)) !== null) {
    const names = match[2].split(",").map((name) => name.trim());
    names.forEach((name) => {
      if (/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
        variables.add(name);
      }
    });
  }

  return variables;
}

/**
 * Extracts all variable names from an array of code strings
 */
export function extractAllVariableNames(codes: string[]): Set<string> {
  const allVariables = new Set<string>();

  for (const code of codes) {
    const variables = extractVariableNamesFromCode(code);
    variables.forEach((v) => allVariables.add(v));
  }

  return allVariables;
}

/**
 * Generates a unique variable name by appending a number if necessary
 *
 * @param baseName - The base name for the variable (e.g., "slider")
 * @param existingNames - Set of existing variable names in the notebook
 * @returns A unique variable name (e.g., "slider", "slider_2", "slider_3", etc.)
 */
export function generateUniqueVariableName(
  baseName: string,
  existingNames: Set<string>,
): string {
  // If the base name is available, use it
  if (!existingNames.has(baseName)) {
    return baseName;
  }

  // Otherwise, find the next available number
  let counter = 2;
  let candidateName = `${baseName}_${counter}`;

  while (existingNames.has(candidateName)) {
    counter++;
    candidateName = `${baseName}_${counter}`;
  }

  return candidateName;
}
