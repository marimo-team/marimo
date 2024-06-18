/* Copyright 2024 Marimo. All rights reserved. */

import { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import React, {
  PropsWithChildren,
  useCallback,
  useEffect,
  useMemo,
} from "react";
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
  let favicon: HTMLLinkElement | null =
    document.querySelector("link[rel~='icon']");

  if (!favicon) {
    favicon = document.createElement("link");
    favicon.rel = "icon";
    document.getElementsByTagName("head")[0].append(favicon);
  }

  const favicons: Record<string, string> = useMemo(
    () => ({
      idle: "./favicon.ico",
      success: "./circle-check.ico",
      running: "./circle-play.ico",
      error: "./circle-x.ico",
    }),
    [],
  );

  const resetFaviconIfComplete = useCallback(() => {
    if (!isRunning && document.visibilityState == "visible") {
      setTimeout(() => {
        favicon.href = favicons.idle;
      }, 3000);
    }
  }, [favicon, favicons.idle, isRunning]);

  useEffect(() => {
    if (isRunning) {
      favicon.href = favicons.running;
      return;
    }
    favicon.href = errors.length > 0 ? favicons.error : favicons.success;
    resetFaviconIfComplete();
    return () => {
      favicon.href = favicons.idle;
    };
  }, [isRunning, errors, favicon, favicons, resetFaviconIfComplete]);

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
