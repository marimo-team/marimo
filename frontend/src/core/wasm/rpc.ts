/* Copyright 2024 Marimo. All rights reserved. */
import {
  createRPC,
  createWorkerTransport,
  type RPCOptions,
  type RPCSchema,
} from "rpc-anywhere";
import { Logger } from "@/utils/Logger";
import { TRANSPORT_ID } from "./worker/constants";

export type ParentSchema = RPCSchema<{
  messages: {
    consumerReady: {};
  };
}>;

export function getWorkerRPC<WorkerSchema extends RPCSchema>(worker: Worker) {
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
  } as RPCOptions<ParentSchema, WorkerSchema>);
}
