/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { DatabaseZapIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import React, { useState } from "react";
import { useLocale } from "react-aria";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { ConfirmationButton } from "@/components/ui/confirmation-button";
import { toast } from "@/components/ui/use-toast";
import { cacheInfoAtom } from "@/core/cache/requests";
import { useRequestClient } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import { cn } from "@/utils/cn";
import { formatBytes, formatTime } from "@/utils/formatting";
import { prettyNumber } from "@/utils/numbers";
import { PanelEmptyState } from "./empty-state";

const CachePanel = () => {
  const { clearCache, getCacheInfo } = useRequestClient();
  const cacheInfo = useAtomValue(cacheInfoAtom);
  const [purging, setPurging] = useState(false);
  const { locale } = useLocale();

  const { isPending, isFetching, refetch } = useAsyncData(async () => {
    await getCacheInfo();
    // Artificially spin the icon if the request is really fast
    await new Promise((resolve) => setTimeout(resolve, 500));
  }, []);

  const handlePurge = async () => {
    try {
      setPurging(true);
      await clearCache();
      toast({
        title: "Cache purged",
        description: "All cached data has been cleared",
      });
      // Request updated cache info after purge
      refetch();
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
  if (isPending && !cacheInfo) {
    return <Spinner size="medium" centered={true} />;
  }

  const refreshButton = (
    <Button variant="outline" size="sm" onClick={refetch} disabled={isFetching}>
      {isFetching ? (
        <Spinner size="small" className="w-4 h-4 mr-2" />
      ) : (
        <RefreshCwIcon className="w-4 h-4 mr-2" />
      )}
      Refresh
    </Button>
  );

  if (!cacheInfo) {
    return (
      <PanelEmptyState
        title="No cache data"
        description="Cache information is not available."
        icon={<DatabaseZapIcon />}
        action={refreshButton}
      />
    );
  }

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
        icon={<DatabaseZapIcon />}
        action={refreshButton}
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
            onClick={refetch}
            disabled={isFetching}
          >
            <RefreshCwIcon
              className={cn(
                "h-4 w-4 text-muted-foreground hover:text-foreground",
                isFetching && "animate-[spin_0.5s]",
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
              value={formatTime(totalTime, locale)}
              description="Total execution time saved"
            />
            <StatCard
              label="Hit rate"
              value={
                totalRequests > 0 ? `${prettyNumber(hitRate, locale)}%` : "—"
              }
              description={`${prettyNumber(totalHits, locale)} hits / ${prettyNumber(totalRequests, locale)} total`}
            />
            <StatCard
              label="Cache hits"
              value={prettyNumber(totalHits, locale)}
              description="Successful cache retrievals"
            />
            <StatCard
              label="Cache misses"
              value={prettyNumber(totalMisses, locale)}
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
                value={formatBytes(diskTotal, locale)}
                description={
                  diskToFree > 0
                    ? `${formatBytes(diskToFree, locale)} can be freed`
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
