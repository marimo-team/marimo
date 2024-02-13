/* Copyright 2024 Marimo. All rights reserved. */
import {
  compressToEncodedURIComponent,
  decompressFromEncodedURIComponent,
} from "lz-string";

export interface FileStore {
  saveFile(contents: string): void;
  readFile(): string | null | Promise<string | null>;
}

const KEY = "marimo:file";
const localStorageFileStore: FileStore = {
  saveFile(contents: string) {
    localStorage.setItem(KEY, contents);
  },
  readFile() {
    return localStorage.getItem(KEY);
  },
};

const URL_PARAM_KEY = "code";
const urlFileStore: FileStore = {
  saveFile(contents: string) {
    const url = new URL(location.href);
    const encoded = compressToEncodedURIComponent(contents);
    url.searchParams.set(URL_PARAM_KEY, encoded);
    history.replaceState(null, "", url.toString());
  },
  readFile() {
    const url = new URL(location.href);
    if (!url.searchParams.has(URL_PARAM_KEY)) {
      return null;
    }
    const code = url.searchParams.get(URL_PARAM_KEY);
    if (!code) {
      return null;
    }
    return decompressFromEncodedURIComponent(code);
  },
};

const remoteDefaultFileStore: FileStore = {
  saveFile(contents: string) {
    // Do nothing
  },
  readFile() {
    const baseURI = document.baseURI;
    return fetch(`${baseURI}files/wasm-intro.py`)
      .then((res) => res.text())
      .catch(() => null);
  },
};

const fallbackFileStore: FileStore = {
  saveFile(contents: string) {
    // Do nothing
  },
  readFile() {
    return [
      "import marimo",
      "app = marimo.App()",
      "",
      "@app.cell",
      "def __():",
      "  import marimo as mo",
      "  x = 1 + 1",
      "  x",
      "  return mo,x",
      "",
      'if __name__ == "__main__":',
      "  app.run()",
    ].join("\n");
  },
};

class CompositeFileStore implements FileStore {
  constructor(private stores: FileStore[]) {}

  saveFile(contents: string) {
    this.stores.forEach((store) => store.saveFile(contents));
  }

  readFile() {
    for (const store of this.stores) {
      const contents = store.readFile();
      if (contents) {
        return contents;
      }
    }
    return null;
  }
}

export const fileStore = new CompositeFileStore([
  // Prefer URL param, then local storage, then remote default, then fallback
  urlFileStore,
  localStorageFileStore,
  remoteDefaultFileStore,
  fallbackFileStore,
]);
