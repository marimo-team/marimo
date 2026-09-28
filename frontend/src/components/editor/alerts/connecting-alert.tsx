/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { Button } from "@/components/ui/button";
import { isNotStartedAtom } from "@/core/network/connection";
import { useConnectToRuntime } from "@/core/runtime/config";
import { FloatingAlert } from "./floating-alert";

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
