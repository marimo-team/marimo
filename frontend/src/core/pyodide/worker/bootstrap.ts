/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { APP_FILE_PATH, mountFilesystem } from "./fs";
import { Logger } from "../../../utils/Logger";
import { SerializedBridge } from "./types";

declare let loadPyodide: undefined | (() => Promise<PyodideInterface>);

export async function bootstrap() {
  if (!loadPyodide) {
    throw new Error("loadPyodide is not defined");
  }

  // Load pyodide and micropip
  const pyodide = await loadPyodide();
  await pyodide.loadPackage("micropip");

  // Install marimo
  const marimoWheel =
    process.env.NODE_ENV === "production"
      ? "marimo >= 0.2.5"
      : "http://localhost:8000/dist/marimo-0.2.5-py3-none-any.whl";
  await pyodide.runPythonAsync(`
    import micropip

    micropip.add_mock_package("multiprocessing", "*", modules={
        "multiprocessing": None,
        "multiprocessing.connection": None,
        "multiprocessing.context": None,
        "multiprocessing.managers": None,
        "multiprocessing.pool": None,
        "multiprocessing.sharedctypes": None,
        "multiprocessing.shared_memory": None,
        "multiprocessing.spawn": None,
    })

    await micropip.install(
      [
        # Subset of marimo requirements
        "${marimoWheel}",
        "markdown",
        "jedi",
        "docutils",
        "pymdown-extensions",
        "pygments",
      ],
      deps=False
    );
  `);

  return pyodide;
}

export async function startSession(
  pyodide: PyodideInterface,
  code: string,
): Promise<SerializedBridge> {
  // Set up the filesystem
  await mountFilesystem(pyodide, code);

  // Load packages from the code
  await pyodide.loadPackagesFromImports(code, {
    messageCallback: Logger.log,
    errorCallback: Logger.error,
  });

  const bridge = await pyodide.runPythonAsync(
    `
      print("[py] Starting marimo...")
      import asyncio
      from marimo._pyodide.pyodide_session import create_session, instantiate

      session, bridge = create_session(filename="${APP_FILE_PATH}")
      instantiate(session)
      asyncio.create_task(session.start())

      bridge`,
  );

  return bridge;
}
