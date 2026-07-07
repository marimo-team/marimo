/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import { RuntimeStatusBadge } from "@/components/lifecycle/RuntimeStatusBadge";
import { isWasm } from "@/core/wasm/utils";

/**
 * Footer indicator that surfaces Pyodide initialization progress. Thin
 * wrapper around `<RuntimeStatusBadge>` so the rest of the footer chrome
 * doesn't need to know about adapters.
 */
export const PyodideStatus: React.FC = () => {
  if (!isWasm()) {
    return null;
  }
  return <RuntimeStatusBadge />;
};
