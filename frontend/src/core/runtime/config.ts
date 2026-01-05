/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtom, useAtomValue } from "jotai";
import useEvent from "react-use-event-hook";
import { Logger } from "@/utils/Logger";
import { connectionAtom } from "../network/connection";
import { store } from "../state/jotai";
import { isAppNotStarted } from "../websocket/connection-utils";
import { WebSocketState } from "../websocket/types";
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
      setConnection({ state: WebSocketState.CONNECTING });
      await runtimeManager.init();
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
