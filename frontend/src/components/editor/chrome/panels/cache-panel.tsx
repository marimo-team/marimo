/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { Trash2Icon } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmationButton } from "@/components/ui/confirmation-button";
import { toast } from "@/components/ui/use-toast";
import { cacheInfoAtom } from "@/core/cache/requests";
import { useRequestClient } from "@/core/network/requests";

const CachePanel = () => {
  const client = useRequestClient();
  const cacheInfo = useAtomValue(cacheInfoAtom);

  useEffect(() => {
    // Request cache info when panel mounts
    client.getCacheInfo();
  }, [client]);

  const handlePurge = async () => {
    try {
      await client.clearCache();
      toast({
        title: "Cache purged",
        description: "All cached data has been cleared",
      });
      // Request updated cache info after purge
      client.getCacheInfo();
    } catch (err) {
      toast({
        title: "Error",
        description:
          err instanceof Error ? err.message : "Failed to purge cache",
        variant: "danger",
      });
    }
  };

  if (!cacheInfo) {
    return <div className="p-4">Loading cache info...</div>;
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) {
      return "0 B";
    }
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${Math.round((bytes / k ** i) * 100) / 100} ${sizes[i]}`;
  };

  const formatTime = (seconds: number) => {
    if (seconds < 1) {
      return `${Math.round(seconds * 1000)}ms`;
    }
    if (seconds < 60) {
      return `${Math.round(seconds * 10) / 10}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  const totalHits = cacheInfo.hits;
  const totalMisses = cacheInfo.misses;
  const totalTime = cacheInfo.time;
  const diskTotal = cacheInfo.disk_total;
  const diskToFree = cacheInfo.disk_to_free;

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      <div className="flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold mb-2">Cache Statistics</h3>
          <div className="space-y-1 text-sm">
            <div>Time saved: {formatTime(totalTime)}</div>
            <div>Cache hits: {totalHits}</div>
            <div>Cache misses: {totalMisses}</div>
            {totalHits + totalMisses > 0 && (
              <div>
                Hit rate:{" "}
                {Math.round((totalHits / (totalHits + totalMisses)) * 100)}%
              </div>
            )}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold mb-2">Storage</h3>
          <div className="space-y-1 text-sm">
            <div>Total: {formatBytes(diskTotal)}</div>
            {diskToFree > 0 && (
              <div className="text-muted-foreground">
                Can free: {formatBytes(diskToFree)}
              </div>
            )}
            <div className="flex items-center justify-between mt-2">
              <ConfirmationButton
                title="Purge cache?"
                description="This will permanently delete all cached data. This action cannot be undone."
                confirmText="Purge"
                destructive={true}
                onConfirm={handlePurge}
              >
                <Button variant="destructive" size="sm">
                  <Trash2Icon className="w-4 h-4 mr-2" />
                  Purge
                </Button>
              </ConfirmationButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CachePanel;
