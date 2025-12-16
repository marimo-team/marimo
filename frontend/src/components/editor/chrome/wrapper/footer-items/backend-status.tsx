/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue, useSetAtom } from "jotai";
import { startCase } from "lodash-es";
import { AlertCircleIcon, CheckCircle2Icon, PowerOffIcon } from "lucide-react";
import type React from "react";
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { useConnectToRuntime, useRuntimeManager } from "@/core/runtime/config";
import { store } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import {
  isAppClosing,
  isAppConnected,
  isAppConnecting,
  isAppNotStarted,
} from "@/core/websocket/connection-utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";

const CHECK_HEALTH_INTERVAL_MS = 30_000;

type ConnectionStatus = "healthy" | "unhealthy" | "connecting" | "disconnected";

// Atom to track connection status for use in other components
export const connectionStatusAtom = atom<ConnectionStatus>("connecting");

export function getConnectionStatus(): ConnectionStatus {
  return store.get(connectionStatusAtom);
}

/**
 * Backend connection status indicator for the developer panel header
 */
export const BackendConnectionStatus: React.FC = () => {
  const connection = useAtomValue(connectionAtom).state;
  const runtime = useRuntimeManager();
  const connectToRuntime = useConnectToRuntime();
  const setConnectionStatus = useSetAtom(connectionStatusAtom);

  const { isFetching, error, data, refetch } = useAsyncData(async () => {
    // If the connection is not connected, return
    if (!isAppConnected(connection)) {
      setConnectionStatus("disconnected");
      return;
    }

    // Skip wasm since there is no health check for wasm
    if (isWasm()) {
      setConnectionStatus("healthy");
      return {
        isHealthy: true,
        lastChecked: new Date(),
        error: undefined,
      };
    }

    try {
      const isHealthy = await runtime.isHealthy();
      setConnectionStatus(isHealthy ? "healthy" : "unhealthy");
      return {
        isHealthy,
        lastChecked: new Date(),
        error: undefined,
      };
    } catch (error) {
      setConnectionStatus("unhealthy");
      return {
        isHealthy: false,
        lastChecked: new Date(),
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }, [runtime, connection]);

  useInterval(refetch, {
    delayMs: isAppConnected(connection) ? CHECK_HEALTH_INTERVAL_MS : null,
    whenVisible: true,
  });

  const getStatusInfo = () => {
    if (isAppNotStarted(connection)) {
      return "Not connected to a runtime";
    }

    const baseStatus = startCase(connection.toLowerCase());
    const healthInfo = data?.lastChecked
      ? data.isHealthy
        ? "✓ Healthy"
        : "✗ Unhealthy"
      : "Health: Unknown";

    const errorInfo = error ? `Error: ${error}` : "";

    return [baseStatus, healthInfo, errorInfo].filter(Boolean).join("\n");
  };

  const getStatusIcon = () => {
    if (isFetching || isAppConnecting(connection)) {
      return <Spinner size="small" />;
    }

    if (isAppClosing(connection)) {
      return <Spinner className="text-destructive" size="small" />;
    }

    if (isAppConnected(connection)) {
      if (data?.isHealthy) {
        return <CheckCircle2Icon className="w-4 h-4 text-(--green-9)" />;
      }
      if (data?.lastChecked) {
        return <AlertCircleIcon className="w-4 h-4 text-(--yellow-9)" />;
      }
      return <CheckCircle2Icon className="w-4 h-4" />;
    }
    if (isAppNotStarted(connection)) {
      return <PowerOffIcon className="w-4 h-4" />;
    }

    return <PowerOffIcon className="w-4 h-4 text-red-500" />;
  };

  const handleClick = () => {
    if (isAppNotStarted(connection)) {
      void connectToRuntime();
    } else {
      void refetch();
    }
  };

  return (
    <Tooltip
      content={
        <div className="text-sm whitespace-pre-line">
          {getStatusInfo()}
          {isAppConnected(connection) && (
            <div className="mt-2 text-xs text-muted-foreground">
              Click to refresh health status
            </div>
          )}
        </div>
      }
      data-testid="footer-backend-status"
    >
      <button
        type="button"
        onClick={handleClick}
        className="p-1 hover:bg-accent rounded flex items-center gap-1.5 text-xs text-muted-foreground"
        data-testid="backend-status"
      >
        {getStatusIcon()}
        <span>Kernel</span>
      </button>
    </Tooltip>
  );
};
