/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import type { PropsWithChildren } from "react";
import type { AppConfig } from "@/core/config/config-schema";
import { PyodideLoader } from "@/core/wasm/PyodideLoader";
import {
  type ConnectionStatus,
  WebSocketClosedReason,
  WebSocketState,
} from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import { DynamicFavicon } from "./dynamic-favicon";
import { StatusOverlay } from "./header/status";
import { WrappedWithSidebar } from "./renderers/vertical-layout/sidebar/wrapped-with-sidebar";

interface Props {
  connection: ConnectionStatus;
  isRunning: boolean;
  width: AppConfig["width"];
  onReconnect?: () => void;
}

export const AppContainer: React.FC<PropsWithChildren<Props>> = ({
  width,
  connection,
  isRunning,
  children,
  onReconnect,
}) => {
  const connectionState = connection.state;

  return (
    <>
      <DynamicFavicon isRunning={isRunning} />
      <StatusOverlay
        connection={connection}
        isRunning={isRunning}
        onReconnect={onReconnect}
      />
      <PyodideLoader>
        <WrappedWithSidebar>
          {/** oxlint-ignore-next-line -- ID is used by other components to grab the DOM element */}
          <div
            id="App"
            data-config-width={width}
            data-connection-state={connectionState}
            className={cn(
              "mathjax_ignore",
              connection.state === WebSocketState.CLOSED &&
                connection.code !==
                  WebSocketClosedReason.KERNEL_STARTUP_ERROR &&
                "disconnected",
              "bg-background w-full h-full text-textColor",
              "flex flex-col overflow-y-auto",
              width === "full" && "config-width-full",
              width === "columns"
                ? "overflow-x-auto"
                : "overflow-x-auto sm:overflow-x-hidden",
              "print:height-fit",
            )}
          >
            {children}
          </div>
        </WrappedWithSidebar>
      </PyodideLoader>
    </>
  );
};
