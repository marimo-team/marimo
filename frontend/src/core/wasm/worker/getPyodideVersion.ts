/* Copyright 2026 Marimo. All rights reserved. */
import { version as pyodideVersion } from "pyodide";

const ALLOW_DEV_VERSIONS = false;

export function getPyodideVersion(marimoVersion: string) {
  return marimoVersion.includes("dev") && ALLOW_DEV_VERSIONS
    ? "dev"
    : `v${pyodideVersion}`;
}
