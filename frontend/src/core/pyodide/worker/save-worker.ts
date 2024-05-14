/* Copyright 2024 Marimo. All rights reserved. */

import type { PyodideInterface } from "pyodide";
import { prettyError } from "../../../utils/errors";
import {
  createWorkerParentTransport,
  createRPC,
  createRPCRequestHandler,
  type RPCSchema,
} from "rpc-anywhere";
import { ParentSchema } from "../rpc";
import { Logger } from "../../../utils/Logger";
import { TRANSPORT_ID } from "./constants";
import { getPyodideVersion, importPyodide } from "./getPyodideVersion";
import { SaveKernelRequest } from "@/core/network/types";
import { WasmFileSystem } from "./fs";
import { getController } from "./getController";

/**
 * Web worker responsible for saving the notebook.
 */

declare const self: Window & {
  pyodide: PyodideInterface;
};

// Initialize
async function loadPyodideAndPackages() {
  try {
    // Import pyodide
    const marimoVersion = getMarimoVersion();
    const pyodideVersion = getPyodideVersion(marimoVersion);
    await importPyodide(marimoVersion);

    // Bootstrap the controller
    const controller = await getController(marimoVersion);
    self.controller = controller;
    self.pyodide = await controller.bootstrap({
      version: marimoVersion,
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
    const file = self.pyodide.FS.readFile(filename, { encoding: "utf8" });
    return file;
  },
  readNotebook: async () => {
    await pyodideReadyPromise; // Make sure loading is done
    return WasmFileSystem.readNotebook(self.pyodide);
  },
  saveNotebook: async (opts: SaveKernelRequest) => {
    await pyodideReadyPromise; // Make sure loading is done
    const saveFile = self.pyodide.runPython(`
      from marimo._pyodide.bootstrap import save_file

      save_file
    `);
    await saveFile(JSON.stringify(opts), WasmFileSystem.NOTEBOOK_FILENAME);
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

rpc.send("ready", {});

function getMarimoVersion() {
  return self.name; // We store the version in the worker name
}
