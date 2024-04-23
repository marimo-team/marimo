/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";
import { getFS } from "./getFS";

const NOTEBOOK_FILENAME = "notebook.py";

export async function mountFilesystem(opts: {
  pyodide: PyodideInterface;
  code: string;
  filename: string | null;
}): Promise<{
  content: string;
  filename: string;
}> {
  const { pyodide, filename, code } = opts;
  const FS = getFS(pyodide);

  // This is our home directory
  const mountDir = "/marimo";
  // Mount the filesystem
  await FS.mkdir(mountDir);
  await FS.mount(pyodide.FS.filesystems.IDBFS, { root: "." }, mountDir);

  await syncFileSystem(pyodide, true);

  // Change to the mounted directory
  FS.chdir(mountDir);

  const readIfExist = (filename: string) => {
    try {
      return FS.readFile(filename, { encoding: "utf8" });
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
        content: existingContent,
        filename,
      };
    }
  }

  // If there is no filename, write the code to the last used file
  FS.writeFile(NOTEBOOK_FILENAME, code);
  return {
    content: code,
    filename: NOTEBOOK_FILENAME,
  };
}

export function syncFileSystem(
  pyodide: PyodideInterface,
  populate: boolean,
): Promise<void> {
  // Sync the filesystem. This brings IndexedDBFS up to date with the in-memory filesystem
  // `true` when starting up, `false` when shutting down
  return new Promise<void>((resolve, reject) => {
    getFS(pyodide).syncfs(populate, (err: Error) => {
      if (err) {
        reject(err);
        return;
      }
      resolve();
    });
  });
}
