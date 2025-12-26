/* Copyright 2026 Marimo. All rights reserved. */

export function getMarimoWheel(version: string) {
  if (import.meta.env.DEV && import.meta.env.VITE_WASM_MARIMO_PREBUILT_WHEEL) {
    return "marimo-base";
  }

  if (import.meta.env.DEV) {
    return `http://localhost:8000/dist/marimo-${
      import.meta.env.VITE_MARIMO_VERSION
    }-py3-none-any.whl`;
  }

  return "marimo-base";
}
