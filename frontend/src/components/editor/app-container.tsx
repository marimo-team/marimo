/* Copyright 2024 Marimo. All rights reserved. */

import { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import React, { PropsWithChildren, useEffect } from "react";
import { StatusOverlay } from "./header/status";
import { AppConfig } from "@/core/config/config-schema";
import { WrappedWithSidebar } from "./renderers/vertical-layout/sidebar/wrapped-with-sidebar";
import { PyodideLoader } from "@/core/pyodide/PyodideLoader";
import { useEventListener } from "@/hooks/useEventListener";
import { useCellErrors } from "@/core/cells/cells";

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
  const errors = useCellErrors();

  // Dynamically update favicon for run feedback
  const favicon = document.querySelector(
    "link[rel~='icon']"
  ) as HTMLLinkElement;

  const favicons: Record<string, string> = {
    idle: "./favicon.ico",
    success: "./circle-check.ico",
    running: "./circle-play.ico",
    error: "./circle-x.ico",
  };

  const resetFaviconIfComplete = () => {
    if (!isRunning && document.visibilityState == "visible") {
      setTimeout(() => {
        favicon.href = favicons["idle"];
      }, 3000);
    }
  };

  useEffect(() => {
    if (isRunning) {
      favicon.href = favicons["running"];
      return;
    }
    if (errors.length > 0) {
      favicon.href = favicons["error"];
    } else {
      favicon.href = favicons["success"];
    }
    resetFaviconIfComplete();
    return () => {
      favicon.href = favicons["idle"];
    };
  }, [isRunning]);

  useEventListener(document, "visibilitychange", (_) => {
    resetFaviconIfComplete();
  });

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
              width === "full" && "config-width-full"
            )}
          >
            {children}
          </div>
        </WrappedWithSidebar>
      </PyodideLoader>
    </>
  );
};
