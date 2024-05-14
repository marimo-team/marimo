/* Copyright 2024 Marimo. All rights reserved. */

import { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import React, { PropsWithChildren } from "react";
import { StatusOverlay } from "./header/status";
import { AppConfig } from "@/core/config/config-schema";
import { WrappedWithSidebar } from "./renderers/vertical-layout/sidebar/wrapped-with-sidebar";
import { PyodideLoader } from "@/core/pyodide/PyodideLoader";

interface Props {
  connectionState: WebSocketState;
  isRunning: boolean;
  width: AppConfig["width"];
}

export const AppContainer: React.FC<PropsWithChildren<Props>> = ({
  width,
  connectionState,
  isRunning,
  children,
}) => {
  return (
    <>
      <StatusOverlay state={connectionState} isRunning={isRunning} />
      <PyodideLoader>
        <WrappedWithSidebar>
          <div
            id="App"
            className={cn(
              connectionState === WebSocketState.CLOSED && "disconnected",
              "bg-background w-full h-full text-textColor",
              "flex flex-col overflow-y-auto overflow-x-hidden",
              width === "full" && "config-width-full",
            )}
          >
            {children}
          </div>
        </WrappedWithSidebar>
      </PyodideLoader>
    </>
  );
};
