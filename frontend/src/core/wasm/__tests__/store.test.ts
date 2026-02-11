/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { codeAtom } from "../../saving/file-state";
import { store } from "../../state/jotai";
import {
  CompositeFileStore,
  domElementFileStore,
  localStorageFileStore,
  mountConfigFileStore,
  notebookFileStore,
} from "../store";

describe("localStorageFileStore", () => {
  it("calls set with correct contents on saveFile", () => {
    localStorageFileStore.saveFile("test content");
    expect(localStorageFileStore.readFile()).toBe("test content");
  });
});

describe("domElementFileStore", () => {
  it("does not change anything on save-file", () => {
    const element = document.createElement("marimo-code");
    document.body.replaceChildren(element);
    expect(element.innerHTML).toBe("");
  });

  it("returns correct value from get on readFile", () => {
    const element = document.createElement("marimo-code");
    document.body.replaceChildren(element);
    element.innerHTML = "other content";
    expect(domElementFileStore.readFile()).toBe("other content");
  });
});

describe("CompositeFileStore", () => {
  it("returns correct value from get on readFile", () => {
    const saved = vi.fn();
    const composite = new CompositeFileStore([
      {
        readFile: () => null,
        saveFile: saved,
      },
      {
        readFile: () => "one",
        saveFile: saved,
      },
      {
        readFile: () => "two",
        saveFile: saved,
      },
    ]);

    expect(composite.readFile()).toBe("one");

    composite.saveFile("new content");
    expect(saved).toHaveBeenCalledWith("new content");
    expect(saved).toHaveBeenCalledTimes(3);
  });
});

describe("mountConfigFileStore", () => {
  it("returns null when no code is set", () => {
    store.set(codeAtom, undefined);
    expect(mountConfigFileStore.readFile()).toBeNull();
  });

  it("returns code when set", () => {
    store.set(codeAtom, "print('hello')");
    expect(mountConfigFileStore.readFile()).toBe("print('hello')");
  });

  it("does not save files", () => {
    store.set(codeAtom, "original");
    mountConfigFileStore.saveFile("new content");
    expect(mountConfigFileStore.readFile()).toBe("original");
  });
});

describe("notebookFileStore priority", () => {
  it("prefers mount config over marimo-code and URL", () => {
    store.set(codeAtom, "mount config code");
    const element = document.createElement("marimo-code");
    element.textContent = "marimo-code element";
    document.body.replaceChildren(element);

    expect(notebookFileStore.readFile()).toBe("mount config code");
  });
});
