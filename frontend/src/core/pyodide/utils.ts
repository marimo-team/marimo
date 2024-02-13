/* Copyright 2024 Marimo. All rights reserved. */
export function isPyodide() {
  return window.loadPyodide !== undefined;
}
