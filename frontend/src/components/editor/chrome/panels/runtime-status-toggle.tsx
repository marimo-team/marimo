/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { ChevronDownIcon } from "lucide-react";
import {
  ProgressStatusIcon,
  type ProgressState,
} from "@/components/ui/progress-stages";
import { isConnectedAtom } from "@/core/network/connection";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { sandboxAtom } from "@/core/packages/sandbox-state";
import { cn } from "@/utils/cn";
import type { PanelSection } from "./panel-context";
import { runtimeDetailsExpandedAtom } from "./runtime-details-state";

export function RuntimeStatusToggle({ section }: { section: PanelSection }) {
  const sandbox = useAtomValue(sandboxAtom);
  const notice = useAtomValue(connectionNoticeAtom);
  const [expanded, setExpanded] = useAtom(runtimeDetailsExpandedAtom);
  const connected = useAtomValue(isConnectedAtom);
  const label = sandbox?.backend ? `${sandbox.backend} sandbox` : "Runtime";
  const statusLabel =
    notice?.title ?? (connected ? "Kernel ready" : "Kernel not connected");
  const status: ProgressState = notice
    ? notice.pending
      ? "running"
      : "failed"
    : connected
      ? "succeeded"
      : "waiting";
  return (
    <button
      type="button"
      aria-label={sandbox?.backend ? label : "Runtime details"}
      aria-expanded={expanded}
      aria-controls={`runtime-details-${section}`}
      title={statusLabel}
      className={cn(
        "flex min-w-0 items-center gap-1.5 rounded px-1.5 py-1 text-xs whitespace-nowrap hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring",
        status === "failed" ? "text-(--red-11)" : "text-foreground",
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <ProgressStatusIcon state={status} variant="dot" />
      <output aria-label={statusLabel} className="truncate">
        {label}
      </output>
      <ChevronDownIcon
        aria-hidden={true}
        className={cn(
          "size-3 shrink-0 text-muted-foreground",
          expanded && "rotate-180",
        )}
      />
    </button>
  );
}
