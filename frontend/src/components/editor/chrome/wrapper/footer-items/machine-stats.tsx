/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { CpuIcon, MemoryStickIcon, MicrochipIcon } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { useNumberFormatter } from "react-aria";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import type { UsageResponse } from "@/core/network/types";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";
import { cn } from "@/utils/cn";

export const MachineStats: React.FC = () => {
  const [nonce, setNonce] = useState(0);
  const connection = useAtomValue(connectionAtom);
  const { getUsageStats } = useRequestClient();
  useInterval(
    () => setNonce((nonce) => nonce + 1),
    // Refresh every 10 seconds, or when the document becomes visible
    { delayMs: 10_000, whenVisible: true },
  );

  const { data } = useAsyncData(async () => {
    if (isWasm()) {
      return null;
    }
    if (connection.state !== WebSocketState.OPEN) {
      return null;
    }
    return getUsageStats();
  }, [nonce, connection.state]);

  return (
    <div className="flex gap-2 items-center px-1">
      {data?.gpu && data.gpu.length > 0 && <GPUBar gpus={data.gpu} />}
      {data && (
        <MemoryUsageBar
          memory={data.memory}
          kernel={data.kernel}
          server={data.server}
        />
      )}
      {data && <CPUBar cpu={data.cpu} />}
    </div>
  );
};

const MemoryUsageBar: React.FC<{
  memory: UsageResponse["memory"];
  kernel: UsageResponse["kernel"];
  server: UsageResponse["server"];
}> = ({ memory, kernel, server }) => {
  const { percent, total, available, is_container } = memory;
  const isContainer = is_container === true;
  const roundedPercent = Math.round(percent);
  const memoryLabel = isContainer ? "container memory" : "computer memory";

  const gbFormatter = useNumberFormatter({
    maximumFractionDigits: 2,
  });
  const mbFormatter = useNumberFormatter({
    maximumFractionDigits: 0,
  });

  const formatBytes = (bytes: number): string => {
    if (bytes > 1024 * 1024 * 1024) {
      return `${gbFormatter.format(bytes / (1024 * 1024 * 1024))} GB`;
    }
    return `${mbFormatter.format(bytes / (1024 * 1024))} MB`;
  };

  const formatGB = (bytes: number): string => {
    return gbFormatter.format(bytes / (1024 * 1024 * 1024));
  };

  return (
    <Tooltip
      delayDuration={200}
      content={
        <div className="flex flex-col gap-1">
          <span>
            <b>{memoryLabel}:</b> {formatGB(total - available)} /{" "}
            {formatGB(total)} GB ({roundedPercent}%)
          </span>
          {server?.memory && (
            <span>
              <b>marimo server:</b> {formatBytes(server.memory)}
            </span>
          )}
          {kernel?.memory && (
            <span>
              <b>kernel:</b> {formatBytes(kernel.memory)}
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

  const gbFormatter = useNumberFormatter({
    maximumFractionDigits: 2,
  });
  const mbFormatter = useNumberFormatter({
    maximumFractionDigits: 0,
  });

  const formatBytes = (bytes: number): string => {
    if (bytes > 1024 * 1024 * 1024) {
      return `${gbFormatter.format(bytes / (1024 * 1024 * 1024))} GB`;
    }
    return `${mbFormatter.format(bytes / (1024 * 1024))} MB`;
  };

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
              {formatBytes(gpu.memory.used)} / {formatBytes(gpu.memory.total)} (
              {Math.round(gpu.memory.percent)}%)
            </span>
          ))}
        </div>
      }
    >
      <div className="flex items-center gap-1" data-testid="gpu-bar">
        <MicrochipIcon className="w-4 h-4" />
        <Bar percent={avgPercent} colorClassName="bg-(--grass-9)" />
      </div>
    </Tooltip>
  );
};

const Bar: React.FC<{ percent: number; colorClassName?: string }> = ({
  percent,
  colorClassName,
}) => {
  return (
    <div className="h-3 w-20 bg-(--slate-4) rounded-lg overflow-hidden border">
      <div
        className={cn("h-full bg-primary", colorClassName)}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
};
