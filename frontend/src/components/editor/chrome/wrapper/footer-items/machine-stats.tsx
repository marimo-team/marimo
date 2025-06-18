/* Copyright 2024 Marimo. All rights reserved. */

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { CpuIcon, MemoryStickIcon, MicrochipIcon } from "lucide-react";
import type React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { getUsageStats } from "@/core/network/requests";
import type { UsageResponse } from "@/core/network/types";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";

export const MachineStats: React.FC = (props) => {
  const connection = useAtomValue(connectionAtom);

  const { data: stats } = useQuery({
    queryKey: ["machineStats"],
    queryFn: getUsageStats,
    enabled: !isWasm() && connection.state === WebSocketState.OPEN,
    refetchInterval: 10_000, // refresh every 10 seconds
    refetchIntervalInBackground: false, // but when tab is visible
  });

  return (
    <div className="flex gap-2 items-center px-1">
      {stats?.gpu && stats.gpu.length > 0 && <GPUBar gpus={stats.gpu} />}
      {stats && (
        <MemoryUsageBar
          memory={stats.memory}
          kernel={stats.kernel}
          server={stats.server}
        />
      )}
      {stats && <CPUBar cpu={stats.cpu} />}
    </div>
  );
};

const MemoryUsageBar: React.FC<{
  memory: UsageResponse["memory"];
  kernel: UsageResponse["kernel"];
  server: UsageResponse["server"];
}> = ({ memory, kernel, server }) => {
  const { percent, total, available } = memory;
  const roundedPercent = Math.round(percent);
  return (
    <Tooltip
      delayDuration={200}
      content={
        <div className="flex flex-col gap-1">
          <span>
            <b>computer memory:</b> {asGB(total - available)} / {asGB(total)} GB
            ({roundedPercent}%)
          </span>
          {server?.memory && (
            <span>
              <b>marimo server:</b> {asGBorMB(server.memory)}
            </span>
          )}
          {kernel?.memory && (
            <span>
              <b>kernel:</b> {asGBorMB(kernel.memory)}
            </span>
          )}
        </div>
      }
    >
      <div className="flex items-center gap-1" data-testid="memory-usage-bar">
        <MemoryStickIcon className="w-4 h-4" />
        <Bar percent={roundedPercent} colorClassName="bg-primary" />
      </div>
    </Tooltip>
  );
};

const CPUBar: React.FC<{ cpu: UsageResponse["cpu"] }> = ({ cpu }) => {
  const { percent } = cpu;
  const roundedPercent = Math.round(percent);
  return (
    <Tooltip
      delayDuration={200}
      content={
        <span>
          <b>CPU:</b> {roundedPercent}%
        </span>
      }
    >
      <div className="flex items-center gap-1" data-testid="cpu-bar">
        <CpuIcon className="w-4 h-4" />
        <Bar percent={roundedPercent} colorClassName="bg-primary" />
      </div>
    </Tooltip>
  );
};

interface GPU {
  index: number;
  name: string;
  memory: {
    used: number;
    total: number;
    percent: number;
  };
}

const GPUBar: React.FC<{ gpus: GPU[] }> = ({ gpus }) => {
  const avgPercent = Math.round(
    gpus.reduce((sum: number, gpu: GPU) => sum + gpu.memory.percent, 0) /
      gpus.length,
  );

  return (
    <Tooltip
      delayDuration={200}
      content={
        <div className="flex flex-col gap-1">
          {gpus.map((gpu) => (
            <span key={gpu.index}>
              <b>
                GPU {gpu.index} ({gpu.name}):
              </b>{" "}
              {asGBorMB(gpu.memory.used)} / {asGBorMB(gpu.memory.total)} GB (
              {Math.round(gpu.memory.percent)}%)
            </span>
          ))}
        </div>
      }
    >
      <div className="flex items-center gap-1" data-testid="gpu-bar">
        <MicrochipIcon className="w-4 h-4" />
        <Bar percent={avgPercent} colorClassName="bg-[var(--grass-9)]" />
      </div>
    </Tooltip>
  );
};

const Bar: React.FC<{ percent: number; colorClassName?: string }> = ({
  percent,
  colorClassName,
}) => {
  return (
    <div className="h-3 w-20 bg-[var(--slate-4)] rounded-lg overflow-hidden border">
      <div
        className={cn("h-full bg-primary", colorClassName)}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
};

function asGBorMB(bytes: number): string {
  if (bytes > 1024 * 1024 * 1024) {
    return `${asGB(bytes)} GB`;
  }
  return `${asMB(bytes)} MB`;
}

function asMB(bytes: number) {
  // 0 decimal places
  const format = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  });
  return format.format(bytes / (1024 * 1024));
}

function asGB(bytes: number) {
  // At most 2 decimal places
  const format = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
  });
  return format.format(bytes / (1024 * 1024 * 1024));
}
