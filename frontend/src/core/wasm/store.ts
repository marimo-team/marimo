/* Copyright 2026 Marimo. All rights reserved. */

import {
  compressToEncodedURIComponent,
  decompressFromEncodedURIComponent,
} from "lz-string";
import { codeAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { TypedLocalStorage } from "@/utils/storage/typed";
import { PyodideRouter } from "./router";

export interface FileStore {
  saveFile(contents: string): void;
  readFile(): string | null | Promise<string | null>;
}

const KEY = "marimo:file";
const storage = new TypedLocalStorage<string | null>(null);
export const localStorageFileStore: FileStore = {
  saveFile(contents: string) {
    storage.set(KEY, contents);
  },
  readFile() {
    return storage.get(KEY);
  },
};

const urlFileStore: FileStore = {
  saveFile(contents: string) {
    // Set the code in the URL
    PyodideRouter.setCodeForHash(compressToEncodedURIComponent(contents));
  },
  readFile() {
    const code =
      PyodideRouter.getCodeFromHash() || PyodideRouter.getCodeFromSearchParam();
    if (!code) {
      return null;
    }
    return decompressFromEncodedURIComponent(code);
  },
};

export const domElementFileStore: FileStore = {
  saveFile(contents: string) {
    // Do nothing
  },
  readFile() {
    const element = document.querySelector("marimo-code");
    if (!element) {
      return null;
    }
    return decodeURIComponent(element.textContent || "").trim();
  },
};

const remoteDefaultFileStore: FileStore = {
  saveFile(contents: string) {
    // Do nothing
  },
  readFile() {
    // Only do this on the marimo playground (https://marimo.app)
    if (window.location.hostname !== "marimo.app") {
      return null;
    }
    const url = new URL("files/wasm-intro.py", document.baseURI);
    return fetch(url.toString())
      .then((res) => (res.ok ? res.text() : null))
      .catch(() => null);
  },
};

export const mountConfigFileStore: FileStore = {
  saveFile(_contents: string) {
    // Read-only: mount config code is set via codeAtom
  },
  readFile() {
    return store.get(codeAtom) ?? null;
  },
};

const emptyFileStore: FileStore = {
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
      "  return",
      "",
      'if __name__ == "__main__":',
      "  app.run()",
    ].join("\n");
  },
};

export class CompositeFileStore implements FileStore {
  private stores: FileStore[];
  constructor(stores: FileStore[]) {
    this.stores = stores;
  }

  insert(index: number, store: FileStore) {
    this.stores.splice(index, 0, store);
  }

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

export const notebookFileStore = new CompositeFileStore([
  // Prefer mount config, then <marimo-code>, then URL
  mountConfigFileStore,
  domElementFileStore,
  urlFileStore,
]);

export const fallbackFileStore = new CompositeFileStore([
  // Prefer then local storage, then remote default, then empty
  localStorageFileStore,
  remoteDefaultFileStore,
  emptyFileStore,
]);
