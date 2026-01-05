/* Copyright 2024 Marimo. All rights reserved. */

import { Objects } from "@/utils/objects";
import { memoizeLastValue } from "@/utils/once";
import { waitForKernelToBeInstantiated } from "../kernel/state";
import type { RuntimeManager } from "../runtime/runtime";
import { waitForConnectionOpen } from "./connection";
import type { EditRequests, RunRequests } from "./types";

type AllRequests = EditRequests & RunRequests;

const SKIP_REQUESTS = new Set<keyof AllRequests>([
  "sendRestart",
  "sendCodeCompletionRequest",
]);

const WAIT_FOR_INSTANTIATE_REQUESTS = new Set<keyof AllRequests>([
  "sendDeleteCell",
  "sendInterrupt",
  "sendPdb",
  "sendRun",
  "sendRunScratchpad",
]);

/**
 * Create a lazy requests client.
 * On any request, we will initialize the runtime manager (if not already initialized)
 * and wait for the connection to be open.
 */
export function createLazyRequests(
  delegate: AllRequests,
  getRuntimeManager: () => RuntimeManager,
): AllRequests {
  // Memoize the init call, just once per runtime manager
  const initOnce = memoizeLastValue((runtimeManager: RuntimeManager) => {
    return runtimeManager.init();
  });

  function connectAndThen<T extends (...args: any[]) => Promise<any>>(
    request: T,
    key: keyof AllRequests,
  ): T {
    const wrapped = (async (...args) => {
      // Call init, just once per runtime manager
      // This needs to be a getter because the runtime manager is created lazily.
      await initOnce(getRuntimeManager());
      // Wait for connection to be open
      await waitForConnectionOpen();
      if (WAIT_FOR_INSTANTIATE_REQUESTS.has(key)) {
        await waitForKernelToBeInstantiated();
      }
      // Call the request
      return request(...args);
    }) as T;
    return wrapped;
  }

  return Objects.mapValues(delegate, (value, key) => {
    if (SKIP_REQUESTS.has(key)) {
      return value;
    }
    return connectAndThen(value, key);
  }) as AllRequests;
}
