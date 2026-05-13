/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertCircleIcon } from "lucide-react";
import type React from "react";
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { wasmInitializationAtom, wasmInitStatusAtom } from "@/core/wasm/state";
import { isWasm } from "@/core/wasm/utils";

/**
 * Footer indicator that surfaces Pyodide initialization progress. Mirrors
 * the "Kernel" indicator but tracks the WASM runtime instead of the server
 * connection. Hides itself once Pyodide is ready.
 */
export const PyodideStatus: React.FC = () => {
  const status = useAtomValue(wasmInitStatusAtom);
  const message = useAtomValue(wasmInitializationAtom);

  if (!isWasm() || status === "ready") {
    return null;
  }

  const icon =
    status === "error" ? (
      <AlertCircleIcon className="w-4 h-4 text-destructive" />
    ) : (
      <Spinner size="small" />
    );

  const tooltip = status === "error" ? "Pyodide failed to initialize" : message;

  return (
    <Tooltip
      content={<div className="text-sm whitespace-pre-line">{tooltip}</div>}
      data-testid="footer-pyodide-status"
    >
      <div
        className="p-1 hover:bg-accent rounded flex items-center gap-1.5 text-xs text-muted-foreground"
        data-testid="pyodide-status"
      >
        {icon}
        <span>Pyodide</span>
      </div>
    </Tooltip>
  );
};
