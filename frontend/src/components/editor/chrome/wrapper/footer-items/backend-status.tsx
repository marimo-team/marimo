/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { startCase } from "lodash-es";
import { AlertCircleIcon, CheckCircle2Icon, PowerOffIcon } from "lucide-react";
import type React from "react";
import { Spinner } from "@/components/icons/spinner";
import { connectionAtom } from "@/core/network/connection";
import { useRuntimeManager } from "@/core/runtime/config";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";
import { FooterItem } from "../footer-item";

const CHECK_HEALTH_INTERVAL_MS = 30_000;

export const BackendConnection: React.FC = () => {
  const connection = useAtomValue(connectionAtom).state;
  const runtime = useRuntimeManager();

  const { isFetching, error, data, refetch } = useAsyncData(async () => {
    if (connection !== WebSocketState.OPEN) {
      return;
    }

    if (isWasm()) {
      return {
        isHealthy: true,
        lastChecked: new Date(),
        error: undefined,
      };
    }

    try {
      const isHealthy = await runtime.isHealthy();
      return {
        isHealthy,
        lastChecked: new Date(),
        error: undefined,
      };
    } catch (error) {
      return {
        isHealthy: false,
        lastChecked: new Date(),
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }, [runtime, connection]);

  useInterval(refetch, {
    delayMs:
      connection === WebSocketState.OPEN ? CHECK_HEALTH_INTERVAL_MS : null,
    whenVisible: true,
  });

  const getStatusInfo = () => {
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
    if (isFetching || connection === WebSocketState.CONNECTING) {
      return <Spinner size="small" />;
    }

    if (connection === WebSocketState.CLOSING) {
      return <Spinner className="text-destructive" size="small" />;
    }

    if (connection === WebSocketState.OPEN) {
      if (data?.isHealthy) {
        return <CheckCircle2Icon className="w-4 h-4 text-[var(--green-9)]" />;
      }
      if (data?.lastChecked) {
        return <AlertCircleIcon className="w-4 h-4 text-[var(--yellow-9)]" />;
      }
      return <CheckCircle2Icon className="w-4 h-4" />;
    }

    return <PowerOffIcon className="w-4 h-4 text-red-500" />;
  };

  return (
    <FooterItem
      tooltip={
        <div className="text-sm whitespace-pre-line">
          {getStatusInfo()}
          {connection === WebSocketState.OPEN && (
            <div className="mt-2 text-xs text-muted-foreground">
              Click to refresh health status
            </div>
          )}
        </div>
      }
      selected={false}
      onClick={refetch}
      data-testid="footer-backend-status"
    >
      {getStatusIcon()}
    </FooterItem>
  );
};
