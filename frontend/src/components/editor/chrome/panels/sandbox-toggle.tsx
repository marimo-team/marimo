/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { ChevronDownIcon } from "lucide-react";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { sandboxAtom } from "@/core/packages/sandbox-state";
import { cn } from "@/utils/cn";
import type { PanelSection } from "./panel-context";
import { sandboxDetailsExpandedAtom } from "./sandbox-details-state";

export function SandboxToggle({ section }: { section: PanelSection }) {
  const sandbox = useAtomValue(sandboxAtom);
  const notice = useAtomValue(connectionNoticeAtom);
  const [expanded, setExpanded] = useAtom(sandboxDetailsExpandedAtom);
  if (!sandbox?.backend) {
    return null;
  }
  let status: "pending" | "error" | "healthy";
  if (notice) {
    status = notice.pending ? "pending" : "error";
  } else {
    status = "healthy";
  }
  const getClassName = (): string => {
    if (status === "error") {
      return "bg-(--red-9)";
    }
    if (status === "pending") {
      return "bg-muted-foreground motion-safe:animate-pulse";
    }
    return "bg-(--grass-9)";
  };
  return (
    <button
      type="button"
      aria-label={`${sandbox.backend} sandbox`}
      aria-expanded={expanded}
      aria-controls={`sandbox-details-${section}`}
      title={notice?.title ?? "Sandbox details"}
      className={cn(
        "flex items-center gap-1.5 rounded px-1.5 py-1 text-xs whitespace-nowrap hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring",
        status === "error" ? "text-(--red-11)" : "text-foreground",
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <output
        aria-label={notice?.title ?? "Sandbox healthy"}
        className={cn("size-1.5 shrink-0 rounded-full", getClassName())}
      />
      {sandbox.backend} sandbox
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
