/* Copyright 2024 Marimo. All rights reserved. */
export function getMarimoWheel(version: string) {
  if (!version) {
    return "marimo >= 0.3.0";
  }
  if (version === "local") {
    return "http://localhost:8000/dist/marimo-0.4.4-py3-none-any.whl";
  }
  if (version === "latest") {
    return "marimo";
  }
  return `marimo==${version}`;
}
