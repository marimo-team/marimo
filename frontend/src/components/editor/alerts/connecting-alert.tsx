/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { LoadingEllipsis } from "@/components/icons/loading-ellipsis";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { DelayMount } from "@/components/utils/delay-mount";
import {
  isClosedAtom,
  isConnectingAtom,
  isNotStartedAtom,
} from "@/core/network/connection";
import { useConnectToRuntime } from "@/core/runtime/config";
import { Tooltip } from "../../ui/tooltip";
import { FloatingAlert } from "./floating-alert";

const SHORT_DELAY_MS = 1000; // 1 second
const LONG_DELAY_MS = 5000; // 5 seconds

export const ConnectingAlert: React.FC = () => {
  const isConnecting = useAtomValue(isConnectingAtom);
  const isClosed = useAtomValue(isClosedAtom);

  if (isConnecting) {
    return (
      <>
        <DelayMount milliseconds={SHORT_DELAY_MS}>
          <div className="absolute top-4 m-0 flex items-center min-h-[28px] left-1/2 transform -translate-x-1/2 z-200 ">
            <Tooltip content="Connecting to a marimo runtime">
              <div className="flex items-center">
                <LoadingEllipsis size={5} className="text-yellow-500" />
              </div>
            </Tooltip>
          </div>
        </DelayMount>
        <FloatingAlert show={isConnecting} delayMs={LONG_DELAY_MS}>
          <div className="flex items-center gap-2">
            <Spinner className="h-4 w-4" />
            <p>Connecting to a marimo runtime ...</p>
          </div>
        </FloatingAlert>
      </>
    );
  }

  if (isClosed) {
    return (
      <FloatingAlert show={isClosed} kind="danger">
        <div className="flex items-center gap-2">
          <p>Failed to connect.</p>
        </div>
      </FloatingAlert>
    );
  }
};

export const NotStartedConnectionAlert: React.FC = () => {
  const isNotStarted = useAtomValue(isNotStartedAtom);
  const connectToRuntime = useConnectToRuntime();

  if (isNotStarted) {
    return (
      <FloatingAlert show={isNotStarted} kind="info">
        <div className="flex items-center gap-2">
          <p>Not connected to a runtime.</p>
          <Button variant="link" onClick={connectToRuntime}>
            Click to connect
          </Button>
        </div>
      </FloatingAlert>
    );
  }

  return null;
};
