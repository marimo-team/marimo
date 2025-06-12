/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { FloatingAlert } from "./floating-alert";
import { isConnectingAtom } from "@/core/network/connection";
import { Spinner } from "@/components/icons/spinner";

const DELAY_MS = 1000; // 1 second

export const ConnectingAlert: React.FC = () => {
  const isConnecting = useAtomValue(isConnectingAtom);

  return (
    <FloatingAlert title="Connecting" show={isConnecting} delayMs={DELAY_MS}>
      <div className="flex items-center gap-2">
        <Spinner className="h-4 w-4" />
        <p>Establishing a connection to a marimo runtime...</p>
      </div>
    </FloatingAlert>
  );
};
