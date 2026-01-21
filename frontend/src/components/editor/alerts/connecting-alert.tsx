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
import { Banner } from "@/plugins/impl/common/error-banner";
import { Tooltip } from "../../ui/tooltip";
import { FloatingAlert } from "./floating-alert";

const SHORT_DELAY_MS = 1000; // 1 second
const LONG_DELAY_MS = 5000; // 5 seconds

export const ConnectingAlert: React.FC = () => {
  const isConnecting = useAtomValue(isConnectingAtom);
  const isClosed = useAtomValue(isClosedAtom);

  if (isConnecting) {
    const subtleNotification = (
      <Tooltip content="Connecting to a marimo runtime">
        <div className="flex items-center">
          <LoadingEllipsis size={5} className="text-yellow-500" />
        </div>
      </Tooltip>
    );

    const longNotification = (
      <Banner
        kind="info"
        className="flex flex-col rounded py-2 px-4 animate-in slide-in-from-top w-fit"
      >
        <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
          <div className="flex items-center gap-2">
            <Spinner className="h-4 w-4" />
            <p>Connecting to a marimo runtime ...</p>
          </div>
        </div>
      </Banner>
    );

    // This waits for 1 second to show the subtle notification, then shows the long notification after 5 seconds.
    return (
      <DelayMount milliseconds={SHORT_DELAY_MS}>
        <div className="m-0 flex items-center min-h-[28px] fixed top-5 left-1/2 transform -translate-x-1/2 z-200">
          <DelayMount
            milliseconds={LONG_DELAY_MS}
            fallback={subtleNotification}
          >
            {longNotification}
          </DelayMount>
        </div>
      </DelayMount>
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
