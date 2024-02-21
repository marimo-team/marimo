/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { mountFilesystem } from "./fs";
import { Logger } from "../../../utils/Logger";
import { SerializedBridge } from "./types";

declare let loadPyodide:
  | undefined
  | ((opts: { packages: string[] }) => Promise<PyodideInterface>);

export async function bootstrap() {
  if (!loadPyodide) {
    throw new Error("loadPyodide is not defined");
  }

  // Load pyodide and packages
  const pyodide = await loadPyodide({
    // Perf: These get loaded while pyodide is being bootstrapped
    // The packages can be found here: https://pyodide.org/en/stable/usage/packages-in-pyodide.html
    packages: ["micropip", "docutils", "Pygments"],
  });

  // Install marimo and its dependencies
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
    micropip.add_mock_package("jedi", "*", modules={
        "jedi": None,
        "jedi.api": None,
    })

    await micropip.install(
      [
        # Subset of marimo requirements
        "${marimoWheel}",
        "markdown",
        "pymdown-extensions",
      ],
      deps=False
    );
  `);

  return pyodide;
}

export async function startSession(
  pyodide: PyodideInterface,
  opts: {
    code: string | null;
    fallbackCode: string;
    filename: string | null;
  },
): Promise<SerializedBridge> {
  // Set up the filesystem
  const { filename, content } = await mountFilesystem({ pyodide, ...opts });

  // Load packages from the code
  await pyodide.loadPackagesFromImports(content, {
    messageCallback: Logger.log,
    errorCallback: Logger.error,
  });

  const bridge = await pyodide.runPythonAsync(
    `
      print("[py] Starting marimo...")
      import asyncio
      from marimo._pyodide.pyodide_session import create_session, instantiate

      session, bridge = create_session(filename="${filename}")
      instantiate(session)
      asyncio.create_task(session.start())

      bridge`,
  );

  return bridge;
}
