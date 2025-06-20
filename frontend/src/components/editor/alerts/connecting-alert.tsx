/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { LoadingEllipsis } from "@/components/icons/loading-ellipsis";
import { isConnectingAtom } from "@/core/network/connection";
import { DelayMount } from "@/components/utils/delay-mount";
import { Tooltip } from "../../ui/tooltip";

const DELAY_MS = 1000; // 1 second

export const ConnectingAlert: React.FC = () => {
  const isConnecting = useAtomValue(isConnectingAtom);

  return (
    isConnecting && (
      <DelayMount milliseconds={DELAY_MS}>
        <div className="absolute top-4 m-0 flex items-center min-h-[28px] left-1/2 transform -translate-x-1/2 z-[200] ">
          <Tooltip content="Connecting to a marimo runtime">
            <div className="flex items-center">
              <LoadingEllipsis size={5} className="text-yellow-500" />
            </div>
          </Tooltip>
        </div>
      </DelayMount>
    )
  );
};
