/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue, useSetAtom } from "jotai";
import { AlertCircleIcon, CheckCircle2Icon } from "lucide-react";
import type React from "react";
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { API } from "@/core/network/api";
import { connectionAtom } from "@/core/network/connection";
import type {
  LspHealthResponse,
  LspRestartRequest,
  LspRestartResponse,
} from "@/core/network/types";
import { isAppConnected } from "@/core/websocket/connection-utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";

const CHECK_LSP_HEALTH_INTERVAL_MS = 60_000;

export const lspHealthAtom = atom<LspHealthResponse | null>(null);

export const LspStatus: React.FC = () => {
  const connection = useAtomValue(connectionAtom).state;
  const setLspHealth = useSetAtom(lspHealthAtom);

  const { isFetching, data, refetch } = useAsyncData(async () => {
    if (!isAppConnected(connection)) {
      return null;
    }

    try {
      const health = await API.get<LspHealthResponse>("/lsp/health");
      setLspHealth(health);
      return health;
    } catch {
      return null;
    }
  }, [connection]);

  useInterval(refetch, {
    delayMs: isAppConnected(connection) ? CHECK_LSP_HEALTH_INTERVAL_MS : null,
    whenVisible: true,
  });

  const handleRestart = async () => {
    try {
      const result = await API.post<LspRestartRequest, LspRestartResponse>(
        "/lsp/restart",
        {},
      );

      if (result.success) {
        toast({
          title: "LSP Servers Restarted",
          description:
            result.restarted.length > 0
              ? `Restarted: ${result.restarted.join(", ")}`
              : "No servers needed restart",
        });
      } else {
        toast({
          variant: "danger",
          title: "LSP Restart Failed",
          description: Object.entries(result.errors ?? {})
            .map(([k, v]) => `${k}: ${v}`)
            .join("\n"),
        });
      }

      // Refresh health status
      refetch();
    } catch (error) {
      toast({
        variant: "danger",
        title: "LSP Restart Failed",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    }
  };

  // Don't show if no LSP servers are configured
  if (!data || data.servers.length === 0) {
    return null;
  }

  const getStatusIcon = () => {
    if (isFetching) {
      return <Spinner size="small" />;
    }

    if (!data) {
      return <AlertCircleIcon className="w-4 h-4" />;
    }

    switch (data.status) {
      case "healthy":
        return <CheckCircle2Icon className="w-4 h-4 text-(--green-9)" />;
      case "degraded":
        return <AlertCircleIcon className="w-4 h-4 text-(--yellow-11)" />;
      case "unhealthy":
        return <AlertCircleIcon className="w-4 h-4 text-(--yellow-11)" />;
    }
  };

  const tooltipContent = (
    <div className="text-sm">
      <b>LSP Status</b>
      <div className="mt-1 text-xs space-y-1">
        {data?.servers.map((server) => (
          <div key={server.serverId} className="flex justify-between gap-2">
            <span>{server.serverId}</span>
            <span
              className={
                server.isResponsive ? "text-(--green-9)" : "text-(--red-9)"
              }
            >
              {server.isResponsive
                ? `✓ OK${server.lastPingMs == null ? "" : ` (${server.lastPingMs.toFixed(0)}ms)`}`
                : server.hasFailed
                  ? "✗ Failed"
                  : "✗ Not responding"}
            </span>
          </div>
        ))}
      </div>
      {data?.status === "healthy" ? null : (
        <div className="mt-2 text-xs text-muted-foreground">
          Click to restart failed servers
        </div>
      )}
    </div>
  );

  const handleClick = () => {
    if (data?.status !== "healthy") {
      void handleRestart();
    }
  };

  return (
    <Tooltip content={tooltipContent} data-testid="footer-lsp-status">
      <button
        type="button"
        onClick={handleClick}
        className="p-1 hover:bg-accent rounded flex items-center gap-1.5 text-xs text-muted-foreground"
        data-testid="lsp-status"
      >
        {getStatusIcon()}
        <span>LSP</span>
      </button>
    </Tooltip>
  );
};
