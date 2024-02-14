/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";

export const APP_FILE_PATH = "notebook.py";

export async function mountFilesystem(
  pyodide: PyodideInterface,
  contents: string,
): Promise<string> {
  const mountDir = "/marimo";
  await pyodide.FS.mkdir(mountDir);
  await pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, { root: "." }, mountDir);

  // Change directory to /marimo
  pyodide.runPython(`
  import os
  os.chdir('/marimo')
  `);

  // Check if or write the default app.py
  if (!(await pyodide.FS.analyzePath(APP_FILE_PATH).exists)) {
    await pyodide.FS.writeFile(APP_FILE_PATH, contents, { encoding: "utf8" });
  }

  return contents || "";
}
