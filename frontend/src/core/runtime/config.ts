/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtom, useAtomValue } from "jotai";
import useEvent from "react-use-event-hook";
import { prettyError } from "@/utils/errors";
import { Logger } from "@/utils/Logger";
import { connectionAtom } from "../network/connection";
import { ConnectionClosedReason } from "../notebook/replica";
import { store } from "../state/jotai";
import { isAppNotStarted } from "../session/connection-utils";
import { ConnectionState } from "../session/types";
import { RuntimeManager } from "./runtime";
import type { RuntimeConfig } from "./types";

function getBaseURI(): string {
  const url = new URL(document.baseURI);
  url.search = "";
  url.hash = "";
  return url.toString();
}

export const DEFAULT_RUNTIME_CONFIG: RuntimeConfig = {
  lazy: true,
  url: getBaseURI(),
};

export const runtimeConfigAtom = atom<RuntimeConfig>(DEFAULT_RUNTIME_CONFIG);
const runtimeManagerAtom = atom<RuntimeManager>((get) => {
  const config = get(runtimeConfigAtom);
  return new RuntimeManager(config, config.lazy);
});

export function useRuntimeManager(): RuntimeManager {
  return useAtomValue(runtimeManagerAtom);
}

export function useConnectToRuntime(): () => Promise<void> {
  const runtimeManager = useRuntimeManager();
  const [connection, setConnection] = useAtom(connectionAtom);
  return useEvent(async () => {
    if (isAppNotStarted(connection.state)) {
      setConnection({ state: ConnectionState.CONNECTING });
      await runtimeManager.start();
    } else {
      Logger.log("Runtime already started or starting...");
    }
  });
}

/**
 * Prefer to use useRuntimeManager instead of this function.
 */
export function getRuntimeManager(): RuntimeManager {
  return store.get(runtimeManagerAtom);
}

/**
 * Start a lazy runtime the first time something needs it.
 *
 * The connection can already read as connecting before anyone has asked
 * for the runtime, because the notebook stream waits for the runtime's
 * health and the editor mirrors that wait. So whether the runtime has
 * been asked to start is the runtime's own business, and this only keeps
 * the connection state honest around the attempt. A start that gives up
 * closes the connection with the reason, which leaves the user a way to
 * reconnect instead of a connection that looks like it is still coming up.
 */
export async function startRuntimeIfLazy(): Promise<void> {
  const runtimeManager = getRuntimeManager();
  if (runtimeManager.isServerless || !runtimeManager.isLazy) {
    return;
  }
  if (isAppNotStarted(store.get(connectionAtom).state)) {
    store.set(connectionAtom, { state: ConnectionState.CONNECTING });
  }
  try {
    await runtimeManager.start();
  } catch (error) {
    if (store.get(connectionAtom).state === ConnectionState.CONNECTING) {
      store.set(connectionAtom, {
        state: ConnectionState.CLOSED,
        code: ConnectionClosedReason.KERNEL_STARTUP_ERROR,
        reason: prettyError(error),
      });
    }
    throw error;
  }
}

export function asRemoteURL(path: string): URL {
  if (path.startsWith("http")) {
    return new URL(path);
  }
  let base = getRuntimeManager().httpURL.toString();
  if (base.startsWith("blob:")) {
    // Remove leading blob:
    base = base.replace("blob:", "");
  }
  return new URL(path, base);
}
