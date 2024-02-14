/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { APP_FILE_PATH, mountFilesystem } from "./fs";

declare let loadPyodide: undefined | (() => Promise<PyodideInterface>);

export async function bootstrap() {
  if (!loadPyodide) {
    throw new Error("loadPyodide is not defined");
  }

  // Load pyodide and micropip
  const pyodide = await loadPyodide();
  await pyodide.loadPackage("micropip");

  // Set up the filesystem
  mountFilesystem(pyodide);

  // Install marimo
  const baseUrl =
    process.env.NODE_ENV === "production"
      ? `${window.location.origin}/registry`
      : "http://localhost:8000/dist";
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
        "${baseUrl}/marimo-0.2.4-py3-none-any.whl",
        "markdown",
        "jedi",
        "docutils",
        "pymdown-extensions",
        "pygments",
      ],
      deps=False
    );
  `);

  const bridge = await pyodide.runPythonAsync(
    `
      print("[py] Importing marimo...")
      import asyncio
      from marimo._ast.app import App
      from marimo._pyodide.pyodide_session import create_session, instantiate

      print("[py] Creating session...")
      session, bridge = create_session(filename="${APP_FILE_PATH}")

      print("[py] Starting session...")
      instantiate(session)
      asyncio.create_task(session.start())

      bridge`,
  );

  return {
    bridge,
    pyodide,
  };
}
