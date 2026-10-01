/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { ArrowRightIcon, ChevronRightIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { hasCellsAtom } from "@/core/cells/cells";
import type { AppConfig } from "@/core/config/config-schema";
import { connectionAtom } from "@/core/network/connection";
import { useConnectionNotice } from "@/core/network/useConnectionNotice";
import { sandboxAtom } from "@/core/packages/sandbox-state";
import { WebSocketState } from "@/core/websocket/types";
import { useInterval } from "@/hooks/useInterval";
import { cn } from "@/utils/cn";
import { SandboxErrorOutput } from "../chrome/panels/sandbox-panel";
import { chromeAtom, useChromeActions } from "../chrome/state";
import { VerticalLayoutWrapper } from "../renderers/vertical-layout/vertical-layout-wrapper";
import { ConnectionStatusIcon, StartupProgress } from "./startup-progress";

export const ConnectionNotice = ({
  appConfig,
  onRetry,
}: {
  appConfig: AppConfig;
  onRetry: () => void;
}) => {
  const notice = useConnectionNotice();
  const connection = useAtomValue(connectionAtom);
  const hasCells = useAtomValue(hasCellsAtom);
  const sandbox = useAtomValue(sandboxAtom);
  const chrome = useAtomValue(chromeAtom);
  const packagesOpen =
    (chrome.isSidebarOpen && chrome.selectedPanel === "packages") ||
    (chrome.isDeveloperPanelOpen &&
      chrome.selectedDeveloperPanelTab === "packages");
  const { openApplication } = useChromeActions();

  // Reconnection uses the footer indicator while existing cells stay visible.
  const reconnecting =
    connection.state === WebSocketState.CONNECTING &&
    connection.phase === "reconnecting";

  if (sandbox?.backend && hasCells) {
    const title =
      notice?.ready && notice.kind === "startup" ? "Ready" : notice?.title;
    return (
      <VerticalLayoutWrapper
        appConfig={appConfig}
        // Reserve the status row and gutter so completion never shifts cells.
        className="shrink-0 h-12 pb-0 sm:pb-0 print:hidden"
        innerClassName="pb-0 sm:pb-0 pr-4"
      >
        {notice && !reconnecting && (
          <section aria-label="Notebook startup">
            <button
              type="button"
              onClick={() => openApplication("packages")}
              aria-label={`${title} Open Packages`}
              aria-expanded={packagesOpen}
              className="flex h-6 items-center gap-2 whitespace-nowrap text-xs text-muted-foreground hover:text-foreground rounded focus-visible:outline-2 focus-visible:outline-ring"
            >
              <ConnectionStatusIcon notice={notice} />
              <output>{title}</output>
              <ChevronRightIcon className="size-3" aria-hidden={true} />
            </button>
          </section>
        )}
      </VerticalLayoutWrapper>
    );
  }

  if (!notice || (hasCells && reconnecting)) {
    return null;
  }

  const showSteps =
    notice.sandbox &&
    notice.kind === "startup" &&
    (notice.ready ||
      notice.phase === "preparing-environment" ||
      notice.phase === "starting-kernel");
  return (
    <VerticalLayoutWrapper
      appConfig={appConfig}
      className="shrink-0 pb-0 sm:pb-0 print:hidden"
      innerClassName="pb-0 sm:pb-0 pr-4"
    >
      <section
        aria-label="Notebook startup"
        className={cn(
          "text-muted-foreground",
          hasCells
            ? "mt-4 mb-8 border rounded-lg px-5 py-5"
            : "max-w-md mx-auto mt-16 sm:mt-24 px-4",
          hasCells && !notice.pending && "border-(--red-7)",
        )}
      >
        {showSteps ? (
          <StartupProgress notice={notice} surface="notebook" />
        ) : (
          <div role="status" className="flex items-center gap-2.5">
            <ConnectionStatusIcon notice={notice} />
            <h2
              className={cn(
                "text-base",
                notice.pending || notice.ready
                  ? "font-normal text-foreground"
                  : "font-medium text-(--red-11)",
              )}
            >
              {notice.title}
            </h2>
          </div>
        )}
        <div className={showSteps ? "mt-8" : "ml-6.5"}>
          {!showSteps && (
            <p
              className={cn(
                "mt-3 text-sm leading-7",
                !notice.pending && "text-foreground",
              )}
            >
              {notice.description}
            </p>
          )}
          {!notice.sandbox && notice.error && (
            <SandboxErrorOutput error={notice.error} />
          )}
          <div
            className={cn(
              "flex flex-wrap items-center gap-x-6 gap-y-3",
              showSteps ? "border-t border-border/60 pt-4" : "mt-5",
            )}
          >
            {!notice.ready &&
              !packagesOpen &&
              (notice.sandbox || notice.pending) && (
                <Button
                  variant="text"
                  size="xs"
                  className={cn(
                    "p-0 text-xs gap-1.5",
                    showSteps ? "h-6" : "h-auto",
                  )}
                  onClick={() => openApplication("packages")}
                >
                  {notice.pending ? "View setup details" : "Open Packages"}
                  <ArrowRightIcon className="size-3" aria-hidden={true} />
                </Button>
              )}
            {!notice.pending && !notice.sandbox && (
              <Button variant="outline" size="xs" onClick={onRetry}>
                Try again
              </Button>
            )}
            {notice.pending && (
              <div className={showSteps ? "ml-auto" : undefined}>
                <StartupElapsedTime />
              </div>
            )}
          </div>
        </div>
      </section>
    </VerticalLayoutWrapper>
  );
};

function StartupElapsedTime() {
  const [startedAt] = useState(Date.now);
  const [seconds, setSeconds] = useState(0);
  useInterval(() => setSeconds(Math.floor((Date.now() - startedAt) / 1000)), {
    delayMs: 1000,
    whenVisible: true,
  });
  const duration =
    seconds < 60
      ? `${seconds}s`
      : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return (
    <span
      className="text-xs text-muted-foreground/70 tabular-nums"
      aria-live="off"
    >
      Elapsed {duration}
    </span>
  );
}
