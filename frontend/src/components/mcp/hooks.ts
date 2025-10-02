/* Copyright 2024 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import { useState } from "react";
import { API } from "@/core/network/api";
import { useAsyncData } from "@/hooks/useAsyncData";
import { toast } from "../ui/use-toast";

export type MCPStatus = components["schemas"]["MCPStatusResponse"];
export type MCPRefreshResponse = components["schemas"]["MCPRefreshResponse"];

/**
 * Hook to fetch MCP server status
 */
export function useMCPStatus() {
  return useAsyncData<MCPStatus>(async () => {
    return API.get<MCPStatus>("/ai/mcp/status");
  }, []);
}

/**
 * Hook to refresh MCP server configuration
 */
export function useMCPRefresh() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = async () => {
    setIsRefreshing(true);
    try {
      await API.post<object, MCPRefreshResponse>("/ai/mcp/refresh", {});
      toast({
        title: "MCP refreshed",
        description: "MCP server configuration has been refreshed successfully",
      });
    } catch (error) {
      toast({
        title: "Refresh failed",
        description:
          error instanceof Error ? error.message : "Failed to refresh MCP",
        variant: "danger",
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  return { refresh, isRefreshing };
}
