/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Whether the current environment is in the VSCode extension
 */
export function isInVscodeExtension(): boolean {
  // We check if the document has a data-vscode-theme-kind attribute
  return document.querySelector("[data-vscode-theme-kind]") !== null;
}
