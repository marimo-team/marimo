/* Copyright 2026 Marimo. All rights reserved. */

import type { unstable_NotebookCall } from "@marimo-team/client";
import type { PyodideInterface } from "pyodide";
import {
  createRPC,
  createRPCRequestHandler,
  createWorkerParentTransport,
  type RPCSchema,
} from "rpc-anywhere";
import type { UserConfig } from "@/core/config/config-schema";
import type {
  ListPackagesResponse,
  PackageOperationResponse,
  NotebookDocumentTransactionRequest,
  SaveNotebookRequest,
} from "@/core/network/types";
import { decodeUtf8 } from "@/utils/strings";
import { Deferred } from "../../../utils/Deferred";
import { prettyError } from "../../../utils/errors";
import { invariant } from "../../../utils/invariant";
import { Logger } from "../../../utils/Logger";
import type { ParentSchema } from "../rpc";
import type { WasmRuntimeConfig } from "../runtime-config";
import { TRANSPORT_ID } from "./constants";
import { WasmFileSystem } from "./fs";
import { getController } from "./getController";
import { getPyodideVersion } from "./getPyodideVersion";
import { t } from "./tracer";
import type {
  BridgePayload,
  RawBridge,
  WasmSession,
  WasmController,
} from "./types";
import { shouldLoadDuckDBPackages } from "../utils";

/**
 * Web worker responsible for running the notebook.
 */

declare const self: Window & {
  pyodide: PyodideInterface;
  controller: WasmController;
};

const workerInitSpan = t.startSpan("worker:init");

const runtimeConfig = new Deferred<WasmRuntimeConfig>();

// Initialize pyodide
async function loadPyodideAndPackages() {
  try {
    const config = await runtimeConfig.promise;
    const pyodideVersion = getPyodideVersion(config.version);
    const controller = await t.wrapAsync(getController)(config.version);
    self.controller = controller;
    rpc.send.initializingMessage({
      message: "Loading marimo...",
    });
    self.pyodide = await t.wrapAsync(controller.bootstrap.bind(controller))({
      ...config,
      pyodideVersion: pyodideVersion,
    });
  } catch (error) {
    Logger.error("Error bootstrapping", error);
    rpc.send.initializedError({
      error: prettyError(error),
    });
  }
}

const sessionReady = new Deferred<WasmSession>();
let started = false;

// Handle RPC requests
const notebookSubscriptions = new Map<
  string,
  { promise: Promise<void>; cancel(): void }
>();
async function getNotebook() {
  const session = await sessionReady.promise;
  const notebook = session.bridge.notebook;
  notebook.set_persistence(async (contents, filename) => {
    // Keep file operations in the execution worker from syncing stale source.
    self.pyodide.FS.writeFile(filename, contents);
    self.pyodide.FS.writeFile(WasmFileSystem.NOTEBOOK_FILENAME, contents);
    await rpc.proxy.request.persistNotebook({ filename, contents });
  });
  return notebook;
}

const requestHandler = createRPCRequestHandler({
  notebookInfo: async () => {
    const notebook = await getNotebook();
    try {
      return { id: notebook.id };
    } finally {
      notebook.destroy();
    }
  },
  notebookSubscribe: (request: { id: string; cursor: string | null }) => {
    let canceled = false;
    const subscribing = (async () => {
      const session = await sessionReady.promise;
      const notebook = session.bridge.notebook;
      try {
        await notebook.subscribe(request.id, request.cursor, (event) => {
          rpc.send.notebookEvent({ id: request.id, event });
        });
        if (!canceled) {
          void session.start().catch((error: unknown) => {
            rpc.send.initializedError({ error: prettyError(error) });
          });
        }
      } finally {
        notebook.destroy();
      }
    })();
    notebookSubscriptions.set(request.id, {
      promise: subscribing,
      cancel: () => {
        canceled = true;
      },
    });
    return subscribing.finally(() => notebookSubscriptions.delete(request.id));
  },
  notebookUnsubscribe: async (id: string) => {
    // An RPC timeout can close a reader while its subscription is still opening.
    const pending = notebookSubscriptions.get(id);
    pending?.cancel();
    await pending?.promise.catch(() => undefined);
    const notebook = await getNotebook();
    try {
      notebook.unsubscribe(id);
    } finally {
      notebook.destroy();
    }
  },
  notebookCall: async (call: unstable_NotebookCall): Promise<unknown> => {
    const notebook = await getNotebook();
    try {
      return JSON.parse(await notebook.call(JSON.stringify(call)));
    } finally {
      notebook.destroy();
    }
  },
  /**
   * Start the session
   */
  startSession: async (opts: {
    queryParameters: Record<string, string | string[]>;
    code: string;
    filename: string | null;
    userConfig: UserConfig;
  }) => {
    await pyodideReadyPromise; // Make sure loading is done

    if (started) {
      Logger.warn("Session already started");
      return;
    }

    started = true;
    try {
      invariant(self.controller, "Controller not loaded");
      await self.controller.mountFilesystem?.({
        code: opts.code,
        filename: opts.filename,
      });
      const prepareSession = t.wrapAsync(
        self.controller.prepareSession.bind(self.controller),
      );
      rpc.send.initializingMessage({
        message: "Loading notebook and dependencies...",
      });
      const session = await prepareSession({
        code: opts.code,
        filename: opts.filename,
        queryParameters: opts.queryParameters,
        userConfig: opts.userConfig,
      });
      sessionReady.resolve(session);
      rpc.send.initializingMessage({
        message: "Initializing notebook...",
      });
      rpc.send.initialized({});
      workerInitSpan.end("ok");
    } catch (error) {
      rpc.send.initializedError({
        error: prettyError(error),
      });
      workerInitSpan.end("error");
    }
    return;
  },

  /**
   * Load packages
   */
  loadPackages: async (code: string) => {
    const span = t.startSpan("loadPackages");
    await pyodideReadyPromise; // Make sure loading is done

    if (shouldLoadDuckDBPackages(code)) {
      // Add pandas and duckdb to the code for mo.sql and for remote duckdb sources
      code = `import pandas\n${code}`;
      code = `import duckdb\n${code}`;
      code = `import sqlglot\n${code}`;

      // Polars + SQL requires pyarrow, and installing
      // after notebook load does not work. As a heuristic,
      // if it appears that the notebook uses polars, add pyarrow.
      if (code.includes("polars")) {
        code = `import pyarrow\n${code}`;
      }
    }

    await self.pyodide.loadPackagesFromImports(code, {
      messageCallback: Logger.log,
      errorCallback: Logger.error,
    });
    span.end();
  },

  /**
   * Read a file
   */
  readFile: async (filename: string) => {
    const span = t.startSpan("readFile");
    await pyodideReadyPromise; // Make sure loading is done

    const file = decodeUtf8(self.pyodide.FS.readFile(filename));
    span.end();
    return file;
  },

  /**
   * Set the interrupt buffer
   */
  setInterruptBuffer: async (payload: Uint8Array) => {
    await pyodideReadyPromise; // Make sure loading is done

    self.pyodide.setInterruptBuffer(payload);
  },

  addPackage: async (opts: {
    package: string;
  }): Promise<PackageOperationResponse> => {
    await pyodideReadyPromise; // Make sure loading is done

    const { package: packageName } = opts;
    const packageNameList = packageName.split(" ").map((name) => name.trim());
    const response = await self.pyodide.runPythonAsync(`
      import micropip
      import json
      response = None
      try:
        await micropip.install(${JSON.stringify(packageNameList)})
        response = {"success": True}
      except Exception as e:
        response = {"success": False, "error": str(e)}
      json.dumps(response)
    `);
    return JSON.parse(response) as PackageOperationResponse;
  },

  removePackage: async (opts: {
    package: string;
  }): Promise<PackageOperationResponse> => {
    await pyodideReadyPromise; // Make sure loading is done

    const { package: packageName } = opts;
    const response = await self.pyodide.runPythonAsync(`
        import micropip
        import json
        response = None
        try:
          micropip.uninstall("${packageName}")
          response = {"success": True}
        except Exception as e:
          response = {"success": False, "error": str(e)}
        json.dumps(response)
      `);
    return JSON.parse(response) as PackageOperationResponse;
  },

  listPackages: async (): Promise<ListPackagesResponse> => {
    const span = t.startSpan("listPackages");
    await pyodideReadyPromise; // Make sure loading is done

    const packages = await self.pyodide.runPythonAsync(`
      import json
      import micropip

      packages = micropip.list()
      packages = [
        {"name": p.name, "version": p.version}
        for p in packages.values()
      ]
      json.dumps(sorted(packages, key=lambda pkg: pkg["name"]))
    `);
    span.end();
    return {
      packages: JSON.parse(packages) as ListPackagesResponse["packages"],
    };
  },

  documentTransaction: async (request: NotebookDocumentTransactionRequest) => {
    const notebook = await getNotebook();
    try {
      await notebook.transaction(JSON.stringify(request));
    } finally {
      notebook.destroy();
    }
  },
  setNotebookLayout: async (layout: SaveNotebookRequest["layout"]) => {
    const notebook = await getNotebook();
    try {
      await notebook.set_layout(JSON.stringify(layout));
    } finally {
      notebook.destroy();
    }
  },

  /**
   * Call a function on the bridge
   */
  async bridge<T extends keyof RawBridge>(opts: {
    functionName: keyof RawBridge;
    payload: BridgePayload<T>;
  }): Promise<unknown> {
    const span = t.startSpan("bridge", {
      functionName: opts.functionName,
    });
    await pyodideReadyPromise; // Make sure loading is done

    const { functionName, payload } = opts;

    // Special case to lazily install black on format
    // Don't return early; still need to ask the pyodide kernel to run
    // the formatter
    if (functionName === "format") {
      await self.pyodide.runPythonAsync(`
        import micropip

        try:
          import black
        except ModuleNotFoundError:
          await micropip.install("black")
        `);
    }

    // Script export also parses Markdown frontmatter when present.
    if (
      functionName === "export_markdown" ||
      functionName === "export_script"
    ) {
      await self.pyodide.runPythonAsync(`
        import micropip

        try:
          import yaml
        except ModuleNotFoundError:
          await micropip.install("pyyaml")
        `);
    }

    // Perform the function call to the Python bridge
    const { bridge } = await sessionReady.promise;

    // Serialize the payload
    const payloadString =
      payload == null
        ? null
        : typeof payload === "string"
          ? payload
          : JSON.stringify(payload);

    // Make the request
    const response =
      payloadString == null
        ? // @ts-expect-error ehh TypeScript
          await bridge[functionName]()
        : // @ts-expect-error ehh TypeScript
          await bridge[functionName](payloadString);

    // Sync the filesystem if we're saving, creating, deleting, or renaming a file
    if (namesThatRequireSync.has(functionName)) {
      void WasmFileSystem.persistFilesToRemote(self.pyodide);
    }

    span.end();
    // Post the response back to the main thread
    return typeof response === "string" ? JSON.parse(response) : response;
  },
});

// create the iframe's schema
export type WorkerSchema = RPCSchema<
  {
    messages: {
      notebookEvent: { id: string; event: string };
      // Emitted when the worker is ready
      ready: {};
      // Emitted when the Pyodide is initialized
      initialized: {};
      // Emitted when the Pyodide is initializing, with new messages
      initializingMessage: { message: string };
      // Emitted when the Pyodide fails to initialize
      initializedError: { error: string };
    };
  },
  typeof requestHandler
>;

const rpc = createRPC<WorkerSchema, ParentSchema>({
  transport: createWorkerParentTransport({
    transportId: TRANSPORT_ID,
  }),
  requestHandler,
  // Persistence can include bootstrapping the storage worker.
  maxRequestTime: Infinity,
});

rpc.addMessageListener("bootstrap", (config) => runtimeConfig.resolve(config));

rpc.send("ready", {});

const namesThatRequireSync = new Set<keyof RawBridge>([
  "rename_file",
  "create_file_or_directory",
  "delete_file_or_directory",
  "copy_file_or_directory",
  "move_file_or_directory",
  "update_file",
]);

const pyodideReadyPromise = t.wrapAsync(loadPyodideAndPackages)();
