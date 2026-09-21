/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { ChevronUpIcon, FileCodeIcon, RefreshCwIcon } from "lucide-react";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { isConnectedAtom } from "@/core/network/connection";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "@/core/packages/sandbox-state";
import { cn } from "@/utils/cn";
import {
  ConnectionStatusIcon,
  StartupProgress,
} from "../../alerts/startup-progress";

export function SandboxErrorOutput({ error }: { error: string }) {
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

function SandboxRecovery({ notice }: { notice: DisplayConnectionNotice }) {
  const sandbox = useAtomValue(sandboxAtom);
  const actions = useAtomValue(sandboxActionsAtom);
  if (notice.pending || notice.ready) {
    return null;
  }
  return (
    <>
      <p className="mt-2 text-foreground">{notice.description}</p>
      {notice.error && <SandboxErrorOutput error={notice.error} />}
      <div className="flex items-center gap-2 mt-3">
        <Button
          variant="outline"
          size="xs"
          disabled={!actions || sandbox?.manifest == null}
          onClick={() => actions?.editManifest()}
        >
          Edit manifest…
        </Button>
        <Button
          variant="text"
          size="xs"
          disabled={!actions}
          onClick={() => actions?.sync()}
        >
          Retry sync
        </Button>
      </div>
      {sandbox?.manifest == null && (
        <p className="mt-3 text-xs text-muted-foreground">
          A manifest will be available once this new notebook starts.
        </p>
      )}
    </>
  );
}

export function SandboxStartupPanel({
  notice,
}: {
  notice: DisplayConnectionNotice;
}) {
  const showSteps =
    notice.kind === "startup" &&
    (notice.ready ||
      notice.phase === "preparing-environment" ||
      notice.phase === "starting-kernel");
  return (
    <div className="flex-1 min-h-0 overflow-auto p-6 text-sm">
      {showSteps ? (
        <StartupProgress notice={notice} surface="sidebar" />
      ) : (
        <div className="flex items-center gap-2" role="status">
          <ConnectionStatusIcon notice={notice} />
          <h2>{notice.title}</h2>
        </div>
      )}
      <SandboxRecovery notice={notice} />
    </div>
  );
}

export function SandboxSyncStatus({
  notice,
}: {
  notice: DisplayConnectionNotice;
}) {
  return (
    <div className="border-b px-3 py-3 text-sm shrink-0 max-h-[50%] overflow-auto">
      <output className="flex items-center gap-2 text-xs">
        <ConnectionStatusIcon notice={notice} />
        <span>{notice.title}</span>
      </output>
      <SandboxRecovery notice={notice} />
    </div>
  );
}

export function SandboxFooter() {
  const sandbox = useAtomValue(sandboxAtom);
  const connected = useAtomValue(isConnectedAtom);
  const actions = useAtomValue(sandboxActionsAtom);
  const operation = useAtomValue(sandboxSyncAtom);
  const notice = useAtomValue(connectionNoticeAtom);
  if (!sandbox?.backend) {
    return null;
  }
  const pending = operation.pending || notice?.pending;
  const status = operation.pending
    ? "Syncing sandbox…"
    : (notice?.title ?? (connected ? "Sandbox ready" : "Sandbox not started"));
  return (
    <div className="border-t p-1.5 shrink-0">
      <DropdownMenu>
        <Tooltip content={status}>
          <DropdownMenuTrigger asChild={true}>
            <button
              type="button"
              className="flex items-center gap-2 w-full h-8 px-2 rounded text-xs text-muted-foreground hover:bg-accent data-[state=open]:bg-accent"
              aria-label={`${sandbox.backend} sandbox actions`}
            >
              <span
                role="status"
                aria-label={status}
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  pending
                    ? "bg-amber-500 motion-safe:animate-pulse"
                    : notice
                      ? "bg-(--red-9)"
                      : connected
                        ? "bg-emerald-500"
                        : "bg-muted-foreground",
                )}
              />
              <span className="shrink-0">{sandbox.backend} sandbox</span>
              <span className="ml-auto truncate">
                {pending
                  ? operation.pending
                    ? "Syncing…"
                    : "Starting…"
                  : notice
                    ? "Needs attention"
                    : connected
                      ? "Ready"
                      : ""}
              </span>
              <ChevronUpIcon className="size-3 shrink-0" />
            </button>
          </DropdownMenuTrigger>
        </Tooltip>
        <DropdownMenuContent
          side="top"
          align="start"
          className="w-52"
          sideOffset={8}
        >
          <DropdownMenuItem
            disabled={pending || !actions}
            onSelect={() => {
              void actions?.sync();
            }}
          >
            <RefreshCwIcon className="size-3.5 mr-2" />
            Sync
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!actions || sandbox.manifest === null}
            onSelect={() => {
              void actions?.editManifest();
            }}
          >
            <FileCodeIcon className="size-3.5 mr-2" />
            Edit manifest…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
