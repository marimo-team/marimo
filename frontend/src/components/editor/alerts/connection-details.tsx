/* Copyright 2026 Marimo. All rights reserved. */
import type { PropsWithChildren } from "react";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import { cn } from "@/utils/cn";
import { ConnectionStatusIcon, StartupProgress } from "./startup-progress";

export function ConnectionErrorOutput({ error }: { error: string }) {
  return (
    <pre
      tabIndex={0}
      aria-label="Error details"
      className="mt-3 p-3 rounded border bg-muted/30 text-xs text-muted-foreground whitespace-pre min-w-0 max-w-full max-h-52 overflow-auto"
    >
      {error}
    </pre>
  );
}

export function ConnectionDetails({
  notice,
  surface = "sidebar",
  children,
}: PropsWithChildren<{
  notice: DisplayConnectionNotice;
  surface?: "notebook" | "sidebar";
}>) {
  const showSteps = notice.kind === "startup";
  const failed = !notice.pending && !notice.ready;
  return (
    <div className="min-w-0 text-sm">
      {showSteps ? (
        <StartupProgress notice={notice} surface={surface} />
      ) : (
        <div className="flex items-center gap-2" role="status">
          <ConnectionStatusIcon notice={notice} />
          <h2
            className={cn(
              surface === "notebook" && "text-base",
              failed ? "font-medium text-(--red-11)" : "text-foreground",
            )}
          >
            {notice.title}
          </h2>
        </div>
      )}
      {(failed || (!showSteps && surface === "notebook")) && (
        <p className={cn("mt-2", failed && "text-foreground")}>
          {notice.description}
        </p>
      )}
      {notice.error && (surface === "sidebar" || !notice.sandbox) && (
        <ConnectionErrorOutput error={notice.error} />
      )}
      {children}
    </div>
  );
}
