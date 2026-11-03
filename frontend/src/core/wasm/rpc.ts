/* Copyright 2026 Marimo. All rights reserved. */
import {
  createRPC,
  createWorkerTransport,
  type RPCOptions,
  type RPCSchema,
} from "rpc-anywhere";
import { Logger } from "@/utils/Logger";
import type { WasmRuntimeConfig } from "./runtime-config";
import { TRANSPORT_ID } from "./worker/constants";

export interface PersistNotebookRequest {
  filename: string;
  contents: string;
}

export type ParentSchema = RPCSchema<{
  requests: {
    persistNotebook: { params: PersistNotebookRequest; response: null };
  };
  messages: {
    bootstrap: WasmRuntimeConfig;
  };
}>;

export function getWorkerRPC<WorkerSchema extends RPCSchema>(
  worker: Worker,
  requestHandler?: RPCOptions<ParentSchema, WorkerSchema>["requestHandler"],
  maxRequestTime = 20_000,
) {
  return createRPC<ParentSchema, WorkerSchema>({
    transport: createWorkerTransport(worker, {
      transportId: TRANSPORT_ID,
    }),
    requestHandler,
    maxRequestTime,
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
