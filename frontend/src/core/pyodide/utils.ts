/* Copyright 2024 Marimo. All rights reserved. */
export function isPyodide() {
  return document.querySelector("marimo-wasm") !== null;
}
