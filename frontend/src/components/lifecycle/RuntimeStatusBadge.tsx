/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertCircleIcon } from "lucide-react";
import type React from "react";
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { type AdapterState, runtimeAdapterAtom } from "@/core/runtime/adapter";

/**
 * Footer pill that surfaces the active runtime's connection/initialization
 * status via its adapter. Hides itself once the runtime is ready.
 */
export const RuntimeStatusBadge: React.FC = () => {
  const adapter = useAtomValue(runtimeAdapterAtom);
  const state = useAtomValue(adapter.state);

  if (state.kind === "ready") {
    return null;
  }

  const icon =
    state.kind === "failed" ? (
      <AlertCircleIcon className="w-4 h-4 text-destructive" />
    ) : (
      <Spinner size="small" />
    );

  return (
    <Tooltip
      content={
        <div className="text-sm whitespace-pre-line">
          {tooltipFor(state, adapter.label)}
        </div>
      }
      data-testid="footer-runtime-status"
    >
      <div
        className="p-1 hover:bg-accent rounded flex items-center gap-1.5 text-xs text-muted-foreground"
        data-testid="runtime-status-footer"
      >
        {icon}
        <span>{adapter.label}</span>
      </div>
    </Tooltip>
  );
};

function tooltipFor(state: AdapterState, label: string): string {
  switch (state.kind) {
    case "failed":
      return state.error.message;
    case "connecting":
      return state.progress?.label ?? `${label} starting…`;
    case "ready":
      return `${label} ready`;
  }
}
