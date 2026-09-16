/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { AlertCircleIcon, ArrowRightIcon } from "lucide-react";
import { useState } from "react";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { hasCellsAtom } from "@/core/cells/cells";
import type { AppConfig } from "@/core/config/config-schema";
import { connectionAtom } from "@/core/network/connection";
import { connectionNoticeAtom } from "@/core/network/connection-notice";
import { WebSocketState } from "@/core/websocket/types";
import { useDelayElapsed } from "@/hooks/useDelayElapsed";
import { useInterval } from "@/hooks/useInterval";
import { cn } from "@/utils/cn";
import { SandboxErrorOutput } from "../chrome/panels/sandbox-panel";
import { chromeAtom, useChromeActions } from "../chrome/state";
import { VerticalLayoutWrapper } from "../renderers/vertical-layout/vertical-layout-wrapper";

export const ConnectionNotice = ({
  appConfig,
  onRetry,
}: {
  appConfig: AppConfig;
  onRetry: () => void;
}) => {
  const notice = useAtomValue(connectionNoticeAtom);
  const connection = useAtomValue(connectionAtom);
  const hasCells = useAtomValue(hasCellsAtom);
  const chrome = useAtomValue(chromeAtom);
  const packagesOpen =
    (chrome.isSidebarOpen && chrome.selectedPanel === "packages") ||
    (chrome.isDeveloperPanelOpen &&
      chrome.selectedDeveloperPanelTab === "packages");
  const elapsed = useDelayElapsed(notice?.pending ? 500 : 0);
  const { openApplication } = useChromeActions();

  // Reconnection uses the footer indicator while existing cells stay visible.
  if (
    !notice ||
    !elapsed ||
    (hasCells &&
      connection.state === WebSocketState.CONNECTING &&
      connection.phase === "reconnecting")
  ) {
    return null;
  }

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
            : "max-w-sm mx-auto mt-16 sm:mt-24 px-4",
          hasCells && !notice.pending && "border-(--red-7)",
        )}
      >
        <div role="status" className="flex items-center gap-2.5">
          {notice.pending ? (
            <Spinner className="size-4 shrink-0" aria-hidden={true} />
          ) : (
            <AlertCircleIcon
              className="size-4 shrink-0 text-(--red-11)"
              aria-hidden={true}
            />
          )}
          <h2
            className={cn(
              "text-base",
              notice.pending
                ? "font-normal text-foreground"
                : "font-medium text-(--red-11)",
            )}
          >
            {notice.title}
          </h2>
        </div>
        <div className="ml-6.5">
          <p
            className={cn(
              "mt-3 text-sm leading-7",
              !notice.pending && "text-foreground",
            )}
          >
            {notice.description}
          </p>
          {!notice.sandbox && notice.error && (
            <SandboxErrorOutput error={notice.error} />
          )}
          <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3">
            {!packagesOpen && (notice.sandbox || notice.pending) && (
              <Button
                variant="text"
                size="xs"
                className="h-auto p-0 text-xs gap-1.5"
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
            {notice.pending && <StartupElapsedTime />}
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
