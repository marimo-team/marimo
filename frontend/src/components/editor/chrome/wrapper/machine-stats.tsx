/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { getUsageStats } from "@/core/network/requests";
import type { UsageResponse } from "@/core/network/types";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";
import { useAtomValue } from "jotai";
import { startCase } from "lodash-es";
import {
  CheckCircle2Icon,
  CpuIcon,
  MemoryStickIcon,
  PowerOffIcon,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { AIStatusIcon, CopilotStatusIcon } from "./copilot-status";

export const MachineStats: React.FC = (props) => {
  const [nonce, setNonce] = useState(0);
  const connection = useAtomValue(connectionAtom);
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
    <div className="flex gap-2 items-center">
      {data && (
        <MemoryUsageBar
          memory={data.memory}
          kernel={data.kernel}
          server={data.server}
        />
      )}
      {data && <CPUBar cpu={data.cpu} />}
      <div className="flex items-center">
        <AIStatusIcon />
        <CopilotStatusIcon />
      </div>
      <BackendConnection connection={connection.state} />
    </div>
  );
};

const BackendConnection: React.FC<{ connection: WebSocketState }> = ({
  connection,
}) => {
  return (
    <Tooltip delayDuration={200} content={startCase(connection.toLowerCase())}>
      <div>
        {connection === WebSocketState.OPEN && (
          <CheckCircle2Icon className="w-4 h-4" />
        )}
        {connection === WebSocketState.CLOSED && (
          <PowerOffIcon className="w-4 h-4" />
        )}
        {connection === WebSocketState.CONNECTING && <Spinner size="small" />}
        {connection === WebSocketState.CLOSING && (
          <Spinner className="text-destructive" size="small" />
        )}
      </div>
    </Tooltip>
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
      <div className="flex items-center gap-1">
        <MemoryStickIcon className="w-4 h-4" />
        <Bar percent={roundedPercent} />
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
      <div className="flex items-center gap-1">
        <CpuIcon className="w-4 h-4" />
        <Bar percent={roundedPercent} />
      </div>
    </Tooltip>
  );
};

const Bar: React.FC<{ percent: number }> = ({ percent }) => {
  return (
    <div className="h-3 w-20 bg-[var(--slate-4)] rounded-lg overflow-hidden border">
      <div className="h-full bg-primary" style={{ width: `${percent}%` }} />
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
