/* Copyright 2026 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRestartKernel } from "@/components/editor/actions/useRestartKernel";
import {
  isConnectedAtom,
  startupProgressAtom,
} from "@/core/network/connection";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import type { DisplayConnectionNotice } from "@/core/network/useConnectionNotice";
import {
  preparationAtom,
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
  sandboxSyncOperationAtom,
} from "@/core/packages/sandbox-state";
import { cn } from "@/utils/cn";
import { StartupOutput } from "../../alerts/startup-output";
import { ConnectionDetails } from "../../alerts/connection-details";
import { usePanelSection } from "./panel-context";
import { runtimeDetailsExpandedAtom } from "./runtime-details-state";

function SandboxRecovery({ notice }: { notice: DisplayConnectionNotice }) {
  const sandbox = useAtomValue(sandboxAtom);
  const actions = useAtomValue(sandboxActionsAtom);
  const sync = useAtomValue(sandboxSyncAtom);
  if (notice.pending || notice.ready) {
    return null;
  }
  return (
    <>
      <div className="flex items-center gap-2 mt-3">
        <Button
          variant="outline"
          size="xs"
          disabled={!actions || sandbox?.manifest == null}
          onClick={() => actions?.editManifest()}
        >
          Edit manifest…
        </Button>
        {notice.kind === "sync" && sync.kind === "restart-required" ? (
          <SandboxRestart />
        ) : (
          <Button
            variant="text"
            size="xs"
            disabled={!actions}
            onClick={() => actions?.sync()}
          >
            Retry sync
          </Button>
        )}
      </div>
      {sandbox?.manifest == null && (
        <p className="mt-3 text-xs text-muted-foreground">
          A manifest will be available once this new notebook starts.
        </p>
      )}
    </>
  );
}

function SandboxRestart() {
  const restartKernel = useRestartKernel();
  return (
    <Button variant="text" size="xs" onClick={restartKernel}>
      Restart Kernel
    </Button>
  );
}

function SandboxSyncDetails({
  notice,
}: {
  notice: DisplayConnectionNotice | null;
}) {
  const operation = useAtomValue(sandboxSyncOperationAtom);
  if (!operation && !notice) {
    return null;
  }
  return (
    <div className="mt-5 min-w-0">
      {notice ? (
        <div className="mb-5">
          <ConnectionDetails notice={notice}>
            <SandboxRecovery notice={notice} />
          </ConnectionDetails>
        </div>
      ) : (
        <p className="text-sm">Environment synced</p>
      )}
      <StartupOutput
        key={operation?.operation_id}
        logs={operation?.logs.environment ?? ""}
        state={
          operation?.status.kind === "running"
            ? "running"
            : operation?.status.kind === "succeeded"
              ? "succeeded"
              : "failed"
        }
        label="sandbox sync output"
      />
    </div>
  );
}

export function RuntimeDetails() {
  const section = usePanelSection();
  const sandbox = Boolean(useAtomValue(sandboxAtom)?.backend);
  const connected = useAtomValue(isConnectedAtom);
  const notice = useAtomValue(connectionNoticeAtom);
  const preparation = useAtomValue(preparationAtom);
  const progress = useAtomValue(startupProgressAtom);
  const [expanded, setExpanded] = useAtom(runtimeDetailsExpandedAtom);
  const startup: DisplayConnectionNotice | null =
    notice?.kind === "startup"
      ? { ...notice, ready: false }
      : preparation || progress || (connected && !sandbox)
        ? {
            kind: "startup",
            sandbox,
            title: "Notebook started",
            description: "The notebook is ready to run.",
            pending: false,
            ready: true,
            error: null,
          }
        : null;
  return (
    <section
      id={`runtime-details-${section}`}
      aria-label={sandbox ? "Sandbox details" : "Runtime details"}
      hidden={!expanded}
      className={cn(
        "min-w-0 overflow-auto p-4",
        connected ? "shrink-0 max-h-[65%] border-b" : "flex-1",
      )}
      onPointerDownCapture={() => setExpanded(true)}
      onFocusCapture={() => setExpanded(true)}
    >
      {notice?.kind === "connection" && (
        <div className="mb-5">
          <ConnectionDetails notice={{ ...notice, ready: false }}>
            {sandbox && (
              <SandboxRecovery notice={{ ...notice, ready: false }} />
            )}
          </ConnectionDetails>
        </div>
      )}
      {startup && (
        <ConnectionDetails notice={startup}>
          {sandbox && <SandboxRecovery notice={startup} />}
        </ConnectionDetails>
      )}
      {sandbox && connected && (
        <SandboxSyncDetails
          notice={notice?.kind === "sync" ? { ...notice, ready: false } : null}
        />
      )}
      {sandbox && connected && (!notice || notice.pending) && (
        <SandboxActions />
      )}
      {!notice && !startup && !sandbox && (
        <p className="text-sm text-muted-foreground">
          Not connected to a runtime.
        </p>
      )}
    </section>
  );
}

function SandboxActions() {
  const sandbox = useAtomValue(sandboxAtom);
  const actions = useAtomValue(sandboxActionsAtom);
  const pending = useAtomValue(sandboxSyncAtom).kind === "running";
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
