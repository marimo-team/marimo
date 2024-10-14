/* Copyright 2024 Marimo. All rights reserved. */
export function getMarimoWheel(version: string) {
  if (!version) {
    return "marimo >= 0.3.0";
  }
  if (version === "local") {
    return `http://localhost:8000/dist/marimo-${
      import.meta.env.VITE_MARIMO_VERSION
    }-py3-none-any.whl`;
  }
  if (version === "latest") {
    return "marimo-base";
  }
  return `marimo-base==${version}`;
}
