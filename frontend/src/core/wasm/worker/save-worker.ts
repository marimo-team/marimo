/* Copyright 2026 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import {
  createRPC,
  createRPCRequestHandler,
  createWorkerParentTransport,
  type RPCSchema,
} from "rpc-anywhere";
import { decodeUtf8 } from "@/utils/strings";
import { Deferred } from "../../../utils/Deferred";
import { prettyError } from "../../../utils/errors";
import { Logger } from "../../../utils/Logger";
import type { ParentSchema, PersistNotebookRequest } from "../rpc";
import type { WasmRuntimeConfig } from "../runtime-config";
import { TRANSPORT_ID } from "./constants";
import { WasmFileSystem } from "./fs";
import { getController } from "./getController";
import { getPyodideVersion } from "./getPyodideVersion";

/**
 * Web worker responsible for saving the notebook.
 */

declare const self: Window & {
  pyodide: PyodideInterface;
};

const runtimeConfig = new Deferred<WasmRuntimeConfig>();

// Initialize
async function loadPyodideAndPackages() {
  try {
    // Import pyodide
    const config = await runtimeConfig.promise;
    const pyodideVersion = getPyodideVersion(config.version);

    // Bootstrap the controller
    const controller = await getController(config.version);
    self.controller = controller;
    self.pyodide = await controller.bootstrap({
      ...config,
      pyodideVersion: pyodideVersion,
    });

    // Mount the filesystem
    await controller.mountFilesystem?.({
      code: "",
      filename: null,
    });

    rpc.send.initialized({});
  } catch (error) {
    Logger.error("Error bootstrapping", error);
    rpc.send.initializedError({ error: prettyError(error) });
  }
}

const pyodideReadyPromise = loadPyodideAndPackages();

// Handle RPC requests
const requestHandler = createRPCRequestHandler({
  readFile: async (filename: string) => {
    await pyodideReadyPromise; // Make sure loading is done
    const file = decodeUtf8(self.pyodide.FS.readFile(filename));
    return file;
  },
  readNotebook: async () => {
    await pyodideReadyPromise; // Make sure loading is done
    return WasmFileSystem.readNotebook(self.pyodide);
  },
  writeNotebook: async ({ filename, contents }: PersistNotebookRequest) => {
    await pyodideReadyPromise;
    const directory = filename.substring(0, filename.lastIndexOf("/"));
    if (directory) {
      self.pyodide.FS.mkdirTree(directory);
    }
    self.pyodide.FS.writeFile(filename, contents);
    self.pyodide.FS.writeFile(WasmFileSystem.NOTEBOOK_FILENAME, contents);
    await WasmFileSystem.persistFilesToRemote(self.pyodide);
  },
});

// create the iframe's schema
export type SaveWorkerSchema = RPCSchema<
  {
    messages: {
      // Emitted when the worker is ready
      ready: {};
      // Emitted when the Pyodide is initialized
      initialized: {};
      // Emitted when the Pyodide fails to initialize
      initializedError: { error: string };
    };
  },
  typeof requestHandler
>;

const rpc = createRPC<SaveWorkerSchema, ParentSchema>({
  transport: createWorkerParentTransport({
    transportId: TRANSPORT_ID,
  }),
  requestHandler,
});

rpc.addMessageListener("bootstrap", (config) => runtimeConfig.resolve(config));

rpc.send("ready", {});
