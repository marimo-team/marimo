/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { useDelayElapsed } from "@/hooks/useDelayElapsed";
import { isConnectedAtom } from "./connection";
import {
  type ConnectionNotice,
  connectionNoticeAtom,
} from "./connection-notice";

export type DisplayConnectionNotice = ConnectionNotice & { ready: boolean };

/** Briefly acknowledge completion, but only for setup the user actually saw. */
export function useConnectionNotice(
  delayMs = 500,
): DisplayConnectionNotice | null {
  const notice = useAtomValue(connectionNoticeAtom);
  const connected = useAtomValue(isConnectedAtom);
  const elapsed = useDelayElapsed(notice?.pending ? delayMs : 0);
  const [previous, setPrevious] = useState<ConnectionNotice | null>(null);

  useEffect(() => {
    if (notice || !connected) {
      setPrevious(elapsed ? notice : null);
      return;
    }
    const timeout = setTimeout(() => setPrevious(null), 1500);
    return () => clearTimeout(timeout);
  }, [notice, connected, elapsed]);

  if (notice) {
    return elapsed ? { ...notice, ready: false } : null;
  }
  if (
    connected &&
    previous?.pending &&
    previous.sandbox &&
    previous.kind !== "connection"
  ) {
    return {
      ...previous,
      pending: false,
      ready: true,
      title:
        previous.kind === "sync"
          ? "Environment synced"
          : "Your notebook is ready",
      description: "The notebook is ready to run.",
      error: null,
    };
  }
  return null;
}
