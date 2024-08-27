/* Copyright 2024 Marimo. All rights reserved. */

import { useEffect } from "react";

import { notebookIsRunningAtom, useCellActions } from "./cells/cells";
import type { AppConfig } from "./config/config-schema";
import { RuntimeState } from "./kernel/RuntimeState";
import { CellsRenderer } from "../components/editor/renderers/cells-renderer";
import { useAtomValue } from "jotai";
import { AppContainer } from "@/components/editor/app-container";
import { AppHeader } from "@/components/editor/header/app-header";
import { getSessionId } from "./kernel/session";
import { useMarimoWebSocket } from "./websocket/useMarimoWebSocket";
import { sendComponentValues } from "./network/requests";

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

  return (
    <AppContainer
      connectionState={connection.state}
      isRunning={isRunning}
      width={appConfig.width}
    >
      <AppHeader connection={connection} className={"sm:pt-8"} />
      <CellsRenderer appConfig={appConfig} mode="read" />
    </AppContainer>
  );
};
