/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { decodeUtf8 } from "@/utils/strings";
import { getFS } from "./getFS";

const NOTEBOOK_FILENAME = "notebook.py";
const HOME_DIR = "/marimo";

export const WasmFileSystem = {
  NOTEBOOK_FILENAME,
  HOME_DIR,
  createHomeDir: (pyodide: PyodideInterface) => {
    // Create and change to the home directory
    const FS = getFS(pyodide);
    try {
      FS.mkdirTree(HOME_DIR);
    } catch {
      // Ignore if the directory already exists
    }
    FS.chdir(HOME_DIR);
  },
  mountFS: (pyodide: PyodideInterface) => {
    const FS = getFS(pyodide);
    // Mount the filesystem
    FS.mount(pyodide.FS.filesystems.IDBFS, { root: "." }, HOME_DIR);
  },
  populateFilesToMemory: async (pyodide: PyodideInterface) => {
    await syncFileSystem(pyodide, true);
  },
  persistFilesToRemote: async (pyodide: PyodideInterface) => {
    await syncFileSystem(pyodide, false);
  },
  readNotebook: (pyodide: PyodideInterface) => {
    const FS = getFS(pyodide);
    const absPath = `${HOME_DIR}/${NOTEBOOK_FILENAME}`;
    return decodeUtf8(FS.readFile(absPath));
  },
  initNotebookCode: (opts: {
    pyodide: PyodideInterface;
    code: string;
    filename: string | null;
  }): { code: string; filename: string } => {
    const { pyodide, filename, code } = opts;
    const FS = getFS(pyodide);

    const readIfExist = (filename: string): string | null => {
      try {
        return decodeUtf8(FS.readFile(filename));
      } catch {
        return null;
      }
    };

    // If there is a filename, read the file if it exists
    // We don't want to change the contents of the file if it already exists
    if (filename && filename !== NOTEBOOK_FILENAME) {
      const existingContent = readIfExist(filename);
      if (existingContent) {
        return {
          code: existingContent,
          filename,
        };
      }
    }

    // If there is no filename, write the code to the last used file
    FS.writeFile(NOTEBOOK_FILENAME, code);
    return {
      code: code,
      filename: NOTEBOOK_FILENAME,
    };
  },
};

function syncFileSystem(
  pyodide: PyodideInterface,
  populate: boolean,
): Promise<void> {
  // Sync the filesystem. This brings IndexedDBFS up to date with the in-memory filesystem
  // `true` when starting up, `false` when shutting down
  return new Promise<void>((resolve, reject) => {
    getFS(pyodide).syncfs(populate, (err: unknown) => {
      if (err instanceof Error) {
        reject(err);
        return;
      }
      resolve();
    });
  });
}
