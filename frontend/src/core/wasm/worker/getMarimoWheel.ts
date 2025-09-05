/* Copyright 2024 Marimo. All rights reserved. */

export function getMarimoWheel(version: string) {
  if (import.meta.env.DEV && import.meta.env.VITE_MARIMO_VERSION) {
    return `http://localhost:8000/dist/marimo-${
      import.meta.env.VITE_MARIMO_VERSION
    }-py3-none-any.whl`;
  }
  return "marimo-base";
}
