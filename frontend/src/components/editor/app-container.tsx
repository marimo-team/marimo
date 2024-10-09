/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import type React from "react";
import type { PropsWithChildren } from "react";
import { StatusOverlay } from "./header/status";
import type { AppConfig } from "@/core/config/config-schema";
import { WrappedWithSidebar } from "./renderers/vertical-layout/sidebar/wrapped-with-sidebar";
import { PyodideLoader } from "@/core/wasm/PyodideLoader";
import { DynamicFavicon } from "./dynamic-favicon";

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
      <DynamicFavicon isRunning={isRunning} />
      <StatusOverlay state={connectionState} isRunning={isRunning} />
      <PyodideLoader>
        <WrappedWithSidebar>
          <div
            id="App"
            data-config-width={width}
            data-connection-state={connectionState}
            className={cn(
              connectionState === WebSocketState.CLOSED && "disconnected",
              "bg-background w-full h-full text-textColor",
              "flex flex-col overflow-y-auto overflow-x-auto",
              width === "full" && "config-width-full",
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
