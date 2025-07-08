/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { useEffect } from "react";
import { AppContainer } from "@/components/editor/app-container";
import { AppHeader } from "@/components/editor/header/app-header";
import { Spinner } from "@/components/icons/spinner";
import { DelayMount } from "@/components/utils/delay-mount";
import { CellsRenderer } from "../components/editor/renderers/cells-renderer";
import { notebookIsRunningAtom, useCellActions } from "./cells/cells";
import type { AppConfig } from "./config/config-schema";
import { RuntimeState } from "./kernel/RuntimeState";
import { getSessionId } from "./kernel/session";
import { sendComponentValues } from "./network/requests";
import { isAppConnecting } from "./websocket/connection-utils";
import { useMarimoWebSocket } from "./websocket/useMarimoWebSocket";

interface AppProps {
  appConfig: AppConfig;
}

export const RunApp: React.FC<AppProps> = ({ appConfig }) => {
  const { setCells } = useCellActions();

  // Initialize RuntimeState event-listeners
  useEffect(() => {
    RuntimeState.INSTANCE.start(sendComponentValues);
    return () => {
      RuntimeState.INSTANCE.stop();
    };
  }, []);

  const { connection } = useMarimoWebSocket({
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

  return (
    <AppContainer
      connection={connection}
      isRunning={isRunning}
      width={appConfig.width}
    >
      <AppHeader connection={connection} className={"sm:pt-8"} />
      {renderCells()}
    </AppContainer>
  );
};
