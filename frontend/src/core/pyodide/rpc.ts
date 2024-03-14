/* Copyright 2024 Marimo. All rights reserved. */
import { createWorkerTransport, createRPC, type RPCSchema } from "rpc-anywhere";

import type { WorkerSchema } from "./worker/worker";
import { TRANSPORT_ID } from "./worker/constants";
import { Logger } from "@/utils/Logger";

export type ParentSchema = RPCSchema<{
  messages: {
    consumerReady: {};
  };
}>;

export function getWorkerRPC(worker: Worker) {
  return createRPC<ParentSchema, WorkerSchema>({
    transport: createWorkerTransport(worker, {
      transportId: TRANSPORT_ID,
    }),
    maxRequestTime: 20_000, // 20 seconds
    _debugHooks: {
      onSend: (message) => {
        Logger.debug("[rpc] Parent -> Worker", message);
      },
      onReceive: (message) => {
        Logger.debug("[rpc] Worker -> Parent", message);
      },
    },
  });
}
