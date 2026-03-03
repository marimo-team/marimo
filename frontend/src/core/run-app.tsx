/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { ArrowLeftIcon } from "lucide-react";
import { useEffect } from "react";
import { AppContainer } from "@/components/editor/app-container";
import { AppHeader } from "@/components/editor/header/app-header";
import { Spinner } from "@/components/icons/spinner";
import { buttonVariants } from "@/components/ui/button";
import { DelayMount } from "@/components/utils/delay-mount";
import { cn } from "@/utils/cn";
import { CellsRenderer } from "../components/editor/renderers/cells-renderer";
import { notebookIsRunningAtom, useCellActions } from "./cells/cells";
import type { AppConfig } from "./config/config-schema";
import { RuntimeState } from "./kernel/RuntimeState";
import { getSessionId } from "./kernel/session";
import { useRequestClient } from "./network/requests";
import { isAppConnecting } from "./websocket/connection-utils";
import { useMarimoKernelConnection } from "./websocket/useMarimoKernelConnection";

interface AppProps {
  appConfig: AppConfig;
}

export const RunApp: React.FC<AppProps> = ({ appConfig }) => {
  const { setCells } = useCellActions();
  const { sendComponentValues } = useRequestClient();

  // Initialize RuntimeState event-listeners
  useEffect(() => {
    RuntimeState.INSTANCE.start(sendComponentValues);
    return () => {
      RuntimeState.INSTANCE.stop();
    };
  }, []);

  const { connection } = useMarimoKernelConnection({
    autoInstantiate: true,
    setCells: setCells,
    sessionId: getSessionId(),
  });

  const isRunning = useAtomValue(notebookIsRunningAtom);
  const isConnecting = isAppConnecting(connection.state);

  const renderCells = () => {
    // If we are connecting for more than 2 seconds, show a spinner
    if (isConnecting) {
      return (
        <DelayMount milliseconds={2000} fallback={null}>
          <Spinner className="mx-auto" />
          <p className="text-center text-sm text-muted-foreground mt-2">
            Connecting...
          </p>
        </DelayMount>
      );
    }

    return <CellsRenderer appConfig={appConfig} mode="read" />;
  };

  const galleryHref = (() => {
    if (typeof window === "undefined") {
      return null;
    }
    const url = new URL(window.location.href);
    if (!url.searchParams.has("file")) {
      return null;
    }
    url.searchParams.delete("file");
    const search = url.searchParams.toString();
    return search ? `${url.pathname}?${search}` : url.pathname;
  })();

  return (
    <AppContainer
      connection={connection}
      isRunning={isRunning}
      width={appConfig.width}
    >
      <AppHeader connection={connection} className="sm:pt-8">
        {galleryHref && (
          <div className="flex items-center px-6 pt-4 sm:-mt-8">
            <a
              href={galleryHref}
              aria-label="Back to gallery"
              className={cn(
                buttonVariants({ variant: "text", size: "sm" }),
                "gap-2 px-0 text-muted-foreground hover:text-foreground",
              )}
            >
              <ArrowLeftIcon className="size-4" aria-hidden={true} />
              <span>Back</span>
            </a>
          </div>
        )}
      </AppHeader>
      {renderCells()}
    </AppContainer>
  );
};
