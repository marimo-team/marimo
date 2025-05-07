/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import { useAtomValue } from "jotai";
import { startCase } from "lodash-es";
import { CheckCircle2Icon, PowerOffIcon } from "lucide-react";
import type React from "react";

export const BackendConnection: React.FC = () => {
  const connection = useAtomValue(connectionAtom).state;

  return (
    <Tooltip delayDuration={200} content={startCase(connection.toLowerCase())}>
      <div className="px-2">
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
