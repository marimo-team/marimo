/* Copyright 2024 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";

const FALLBACK_FILE = "notebook.py";

export function getFS(pyodide: PyodideInterface): typeof FS {
  return pyodide.FS;
}

export async function mountFilesystem(opts: {
  pyodide: PyodideInterface;
  code: string | null;
  fallbackCode: string;
  filename: string | null;
}): Promise<{
  content: string;
  filename: string;
}> {
  const { pyodide, filename, code, fallbackCode } = opts;
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

  const content = code || fallbackCode;

  // If there is a filename, read the file if it exists
  // We don't want to change the contents of the file if it already exists
  if (filename && filename !== FALLBACK_FILE) {
    const existingContent = readIfExist(filename);
    if (existingContent) {
      return {
        content: existingContent,
        filename,
      };
    }

    // If the filename does not exist in the FS, write the content to the file
    FS.writeFile(filename, content);
    return {
      content,
      filename,
    };
  }

  // If there is no filename, write the code to the last used file
  FS.writeFile(FALLBACK_FILE, content);
  return {
    content: content,
    filename: FALLBACK_FILE,
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
