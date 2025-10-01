/* Copyright 2024 Marimo. All rights reserved. */

import { Loader2, PlugIcon, RefreshCwIcon } from "lucide-react";
import { API } from "@/core/network/api";
import { cn } from "@/utils/cn";
import { Button } from "../ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";
import { useMCPStatus } from "./hooks";

/**
 * MCP Status indicator component
 * Shows a small icon with status color and a popover with detailed information
 */
export const MCPStatusIndicator: React.FC = () => {
  const { data: status, refetch, isFetching } = useMCPStatus();

  const handleRefresh = async () => {
    try {
      await API.post<object, { success: boolean }>("/ai/mcp/refresh", {});
      toast({
        title: "MCP refreshed",
        description: "MCP server configuration has been refreshed",
      });
      refetch();
    } catch (error) {
      toast({
        title: "Refresh failed",
        description:
          error instanceof Error ? error.message : "Failed to refresh MCP",
        variant: "danger",
      });
    }
  };

  const servers = status?.servers || {};
  const hasServers = Object.keys(servers).length > 0;

  return (
    <Popover>
      <Tooltip content="MCP Status">
        <PopoverTrigger asChild={true}>
          <Button variant="text" size="icon">
            <PlugIcon
              className={cn(
                "h-4 w-4",
                status?.status === "ok" && "text-green-500",
                status?.status === "partial" && "text-yellow-500",
                status?.status === "error" && hasServers && "text-red-500",
              )}
            />
          </Button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent className="w-[320px]" align="start" side="right">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm">MCP Server Status</h4>
            <Button
              variant="ghost"
              size="xs"
              onClick={handleRefresh}
              disabled={isFetching}
            >
              {isFetching ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCwIcon className="h-3 w-3" />
              )}
            </Button>
          </div>
          {status && (
            <div className="text-xs space-y-2">
              {hasServers && (
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Overall:</span>
                  <McpStatusText status={status.status} />
                </div>
              )}
              {status.error && (
                <div className="text-xs text-red-500 bg-red-50 dark:bg-red-950/20 p-2 rounded">
                  {status.error}
                </div>
              )}
              {hasServers && (
                <div className="space-y-1">
                  <div className="text-muted-foreground font-medium">
                    Servers:
                  </div>
                  {Object.entries(servers).map(([name, serverStatus]) => (
                    <div
                      key={name}
                      className="flex justify-between items-center pl-2"
                    >
                      <span className="text-muted-foreground truncate max-w-[180px]">
                        {name}
                      </span>
                      <McpStatusText status={serverStatus} />
                    </div>
                  ))}
                </div>
              )}
              {!hasServers && (
                <div className="text-muted-foreground text-center py-2">
                  No MCP servers configured. <br /> Configure under{" "}
                  <b>Settings &gt; AI &gt; MCP</b>
                </div>
              )}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export const McpStatusText: React.FC<{
  status:
    | "ok"
    | "partial"
    | "error"
    | "failed"
    | "disconnected"
    | "pending"
    | "connected";
}> = ({ status }) => {
  return (
    <span
      className={cn(
        "text-xs font-medium",
        status === "ok" && "text-green-500",
        status === "partial" && "text-yellow-500",
        status === "error" && "text-red-500",
        status === "failed" && "text-red-500",
        status === "disconnected" && "text-gray-500",
        status === "pending" && "text-yellow-500",
        status === "connected" && "text-green-500",
      )}
    >
      {status}
    </span>
  );
};
