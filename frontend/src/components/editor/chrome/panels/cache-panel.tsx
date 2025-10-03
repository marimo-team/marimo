/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { DatabaseIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import React, { useEffect, useState } from "react";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { ConfirmationButton } from "@/components/ui/confirmation-button";
import { toast } from "@/components/ui/use-toast";
import { cacheInfoAtom } from "@/core/cache/requests";
import { useRequestClient } from "@/core/network/requests";
import { cn } from "@/utils/cn";
import { prettyNumber } from "@/utils/numbers";
import { PanelEmptyState } from "./empty-state";

const CachePanel = () => {
  const { clearCache, getCacheInfo } = useRequestClient();
  const cacheInfo = useAtomValue(cacheInfoAtom);
  const [purging, setPurging] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);

  useEffect(() => {
    // Request cache info when panel mounts
    void getCacheInfo();
    setInitialLoad(false);
  }, [getCacheInfo]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await getCacheInfo();
    } finally {
      // Artificially spin the icon if the request is really fast
      setTimeout(() => setRefreshing(false), 500);
    }
  };

  const handlePurge = async () => {
    try {
      setPurging(true);
      await clearCache();
      toast({
        title: "Cache purged",
        description: "All cached data has been cleared",
      });
      // Request updated cache info after purge
      void getCacheInfo();
    } catch (err) {
      toast({
        title: "Error",
        description:
          err instanceof Error ? err.message : "Failed to purge cache",
        variant: "danger",
      });
    } finally {
      setPurging(false);
    }
  };

  // Show spinner only on initial load
  if (initialLoad && !cacheInfo) {
    return <Spinner size="medium" centered={true} />;
  }

  if (!cacheInfo) {
    return (
      <PanelEmptyState
        title="No cache data"
        description="Cache information is not available."
        icon={<DatabaseIcon />}
      />
    );
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0 || bytes === -1) {
      return "0 B";
    }
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const value = bytes / k ** i;
    return `${prettyNumber(value, "en-US")} ${sizes[i]}`;
  };

  const formatTime = (seconds: number) => {
    if (seconds === 0) {
      return "0s";
    }
    if (seconds < 0.001) {
      return `${prettyNumber(seconds * 1_000_000, "en-US")}µs`;
    }
    if (seconds < 1) {
      return `${prettyNumber(seconds * 1000, "en-US")}ms`;
    }
    if (seconds < 60) {
      return `${prettyNumber(seconds, "en-US")}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (minutes < 60) {
      return secs > 0
        ? `${minutes}m ${prettyNumber(secs, "en-US")}s`
        : `${minutes}m`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMins = minutes % 60;
    return remainingMins > 0 ? `${hours}h ${remainingMins}m` : `${hours}h`;
  };

  const totalHits = cacheInfo.hits;
  const totalMisses = cacheInfo.misses;
  const totalTime = cacheInfo.time;
  const diskTotal = cacheInfo.disk_total;
  const diskToFree = cacheInfo.disk_to_free;

  const totalRequests = totalHits + totalMisses;
  const hitRate = totalRequests > 0 ? (totalHits / totalRequests) * 100 : 0;

  // Show empty state if no cache activity
  if (totalRequests === 0) {
    return (
      <PanelEmptyState
        title="No cache activity"
        description="The cache has not been used yet. Cached functions will appear here once they are executed."
        icon={<DatabaseIcon />}
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? (
              <Spinner size="small" className="w-4 h-4 mr-2" />
            ) : (
              <RefreshCwIcon className="w-4 h-4 mr-2" />
            )}
            Refresh
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <div className="flex flex-col gap-4 p-4 h-full">
        {/* Header with Refresh Button */}
        <div className="flex items-center justify-end">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCwIcon
              className={cn(
                "h-4 w-4 text-muted-foreground hover:text-foreground",
                refreshing && "animate-[spin_0.5s]",
              )}
            />
          </Button>
        </div>

        {/* Statistics Section */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground">Statistics</h3>
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              label="Time saved"
              value={formatTime(totalTime)}
              description="Total execution time saved"
            />
            <StatCard
              label="Hit rate"
              value={
                totalRequests > 0 ? `${prettyNumber(hitRate, "en-US")}%` : "—"
              }
              description={`${prettyNumber(totalHits, "en-US")} hits / ${prettyNumber(totalRequests, "en-US")} total`}
            />
            <StatCard
              label="Cache hits"
              value={prettyNumber(totalHits, "en-US")}
              description="Successful cache retrievals"
            />
            <StatCard
              label="Cache misses"
              value={prettyNumber(totalMisses, "en-US")}
              description="Cache not found"
            />
          </div>
        </div>

        {/* Storage Section */}
        {diskTotal > 0 && (
          <div className="space-y-3 pt-2 border-t">
            <h3 className="text-sm font-semibold text-foreground">Storage</h3>
            <div className="grid grid-cols-1 gap-3">
              <StatCard
                label="Disk usage"
                value={formatBytes(diskTotal)}
                description={
                  diskToFree > 0
                    ? `${formatBytes(diskToFree)} can be freed`
                    : "Cache storage on disk"
                }
              />
            </div>
          </div>
        )}

        <div className="my-auto" />

        {/* Actions Section */}
        <div className="pt-2 border-t">
          <ConfirmationButton
            title="Purge cache?"
            description="This will permanently delete all cached data. This action cannot be undone."
            confirmText="Purge"
            destructive={true}
            onConfirm={handlePurge}
          >
            <Button
              variant="outlineDestructive"
              size="xs"
              disabled={purging}
              className="w-full"
            >
              {purging ? (
                <Spinner size="small" className="w-3 h-3 mr-2" />
              ) : (
                <Trash2Icon className="w-3 h-3 mr-2" />
              )}
              Purge Cache
            </Button>
          </ConfirmationButton>
        </div>
      </div>
    </div>
  );
};

const StatCard: React.FC<{
  label: string;
  value: string;
  description?: string;
}> = ({ label, value, description }) => {
  return (
    <div className="flex flex-col gap-1 p-3 rounded-lg border bg-card">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold">{value}</span>
      {description && (
        <span className="text-xs text-muted-foreground">{description}</span>
      )}
    </div>
  );
};

export default CachePanel;
