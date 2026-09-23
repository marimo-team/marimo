/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { RefreshCwIcon } from "lucide-react";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { Button } from "@/components/ui/button";
import {
  isConnectedAtom,
  startupProgressAtom,
} from "@/core/network/connection";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import {
  preparationAtom,
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "@/core/packages/sandbox-state";
import { cn } from "@/utils/cn";
import { usePanelSection } from "./panel-context";
import { sandboxDetailsExpandedAtom } from "./sandbox-details-state";
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

function SandboxStartupPanel({ notice }: { notice: DisplayConnectionNotice }) {
  const showSteps =
    notice.kind === "startup" &&
    (notice.ready ||
      notice.phase === "preparing-environment" ||
      notice.phase === "starting-kernel");
  return (
    <div className="min-w-0 text-sm">
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

function SandboxSyncStatus({ notice }: { notice: DisplayConnectionNotice }) {
  return (
    <div className="mb-5 text-sm">
      <output className="flex items-center gap-2 text-xs">
        <ConnectionStatusIcon notice={notice} />
        <span>{notice.title}</span>
      </output>
      <SandboxRecovery notice={notice} />
    </div>
  );
}

export function SandboxDetails() {
  const section = usePanelSection();
  const connected = useAtomValue(isConnectedAtom);
  const notice = useAtomValue(connectionNoticeAtom);
  const preparation = useAtomValue(preparationAtom);
  const progress = useAtomValue(startupProgressAtom);
  const [expanded, setExpanded] = useAtom(sandboxDetailsExpandedAtom);
  const startup: DisplayConnectionNotice | null =
    notice?.kind === "startup"
      ? { ...notice, ready: false }
      : preparation || progress
        ? {
            kind: "startup",
            sandbox: true,
            title: "Notebook started",
            description: "The notebook is ready to run.",
            pending: false,
            ready: true,
            error: null,
          }
        : null;
  return (
    <section
      id={`sandbox-details-${section}`}
      aria-label="Sandbox details"
      hidden={!expanded}
      className={cn(
        "min-w-0 overflow-auto p-4",
        connected ? "shrink-0 max-h-[65%] border-b" : "flex-1",
      )}
      onPointerDownCapture={() => setExpanded(true)}
      onFocusCapture={() => setExpanded(true)}
    >
      {notice && notice.kind !== "startup" && (
        <SandboxSyncStatus notice={{ ...notice, ready: false }} />
      )}
      {startup && <SandboxStartupPanel notice={startup} />}
      {connected && (!notice || notice.pending) && <SandboxActions />}
    </section>
  );
}

function SandboxActions() {
  const sandbox = useAtomValue(sandboxAtom);
  const actions = useAtomValue(sandboxActionsAtom);
  const { pending } = useAtomValue(sandboxSyncAtom);
  return (
    <div className="flex items-center gap-4 mt-5 border-t pt-3">
      <Button
        variant="text"
        size="xs"
        className="text-muted-foreground gap-1.5 p-0"
        disabled={pending || !actions}
        onClick={() => actions?.sync()}
      >
        <RefreshCwIcon className="size-3" aria-hidden={true} />
        Sync
      </Button>
      <Button
        variant="text"
        size="xs"
        className="text-muted-foreground p-0"
        disabled={!actions || sandbox?.manifest == null}
        onClick={() => actions?.editManifest()}
      >
        Edit manifest…
      </Button>
    </div>
  );
}
