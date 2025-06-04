/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import { useRuntimeManager } from "@/core/runtime/config";
import { useAtomValue } from "jotai";
import { startCase } from "lodash-es";
import { CheckCircle2Icon, PowerOffIcon, AlertCircleIcon } from "lucide-react";
import type React from "react";
import { useState, useEffect } from "react";
import useEvent from "react-use-event-hook";
import { useInterval } from "@/hooks/useInterval";

interface HealthStatus {
  isHealthy: boolean;
  lastChecked: Date | null;
  error?: string;
}

const CHECK_HEALTH_INTERVAL_MS = 30_000;

export const BackendConnection: React.FC = () => {
  const connection = useAtomValue(connectionAtom).state;
  const runtime = useRuntimeManager();
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({
    isHealthy: false,
    lastChecked: null,
  });
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  const checkHealth = useEvent(async () => {
    if (!runtime) {
      return;
    }

    setIsCheckingHealth(true);
    try {
      const isHealthy = await runtime.isHealthy();
      setHealthStatus({
        isHealthy,
        lastChecked: new Date(),
        error: undefined,
      });
    } catch (error) {
      setHealthStatus({
        isHealthy: false,
        lastChecked: new Date(),
        error: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setIsCheckingHealth(false);
    }
  });

  // Initial health check on mount when connection is open
  useEffect(() => {
    if (connection === WebSocketState.OPEN && !healthStatus.lastChecked) {
      checkHealth();
    }
  }, [connection, checkHealth, healthStatus.lastChecked]);

  useInterval(
    () => {
      if (connection === WebSocketState.OPEN) {
        checkHealth();
      }
    },
    {
      delayMs:
        connection === WebSocketState.OPEN ? CHECK_HEALTH_INTERVAL_MS : null,
      whenVisible: true,
    },
  );

  const getStatusInfo = () => {
    const baseStatus = startCase(connection.toLowerCase());
    const healthInfo = healthStatus.lastChecked
      ? `Health: ${healthStatus.isHealthy ? "✓ Healthy" : "✗ Unhealthy"}`
      : "Health: Unknown";

    const lastChecked = healthStatus.lastChecked
      ? `Last checked: ${healthStatus.lastChecked.toLocaleTimeString()}`
      : "";

    const error = healthStatus.error ? `Error: ${healthStatus.error}` : "";

    return [baseStatus, healthInfo, lastChecked, error]
      .filter(Boolean)
      .join("\n");
  };

  const getStatusIcon = () => {
    if (isCheckingHealth || connection === WebSocketState.CONNECTING) {
      return <Spinner size="small" />;
    }

    if (connection === WebSocketState.CLOSING) {
      return <Spinner className="text-destructive" size="small" />;
    }

    if (connection === WebSocketState.OPEN) {
      if (healthStatus.isHealthy) {
        return <CheckCircle2Icon className="w-4 h-4 text-green-500" />;
      }
      if (healthStatus.lastChecked) {
        return <AlertCircleIcon className="w-4 h-4 text-yellow-500" />;
      }
      return <CheckCircle2Icon className="w-4 h-4" />;
    }

    return <PowerOffIcon className="w-4 h-4 text-red-500" />;
  };

  const handleClick = () => {
    if (connection === WebSocketState.OPEN && !isCheckingHealth) {
      checkHealth();
    }
  };

  return (
    <Tooltip
      delayDuration={200}
      content={
        <div className="text-sm whitespace-pre-line">
          {getStatusInfo()}
          {connection === WebSocketState.OPEN && (
            <div className="mt-2 text-xs text-muted-foreground">
              Click to refresh health status
            </div>
          )}
        </div>
      }
    >
      <div
        className={`px-2 ${connection === WebSocketState.OPEN ? "cursor-pointer hover:bg-muted/50 rounded" : ""}`}
        onClick={handleClick}
      >
        {getStatusIcon()}
      </div>
    </Tooltip>
  );
};
