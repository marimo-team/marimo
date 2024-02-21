/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/unbound-method */
import { expect, describe, it, vi } from "vitest";
import {
  localStorageFileStore,
  domElementFileStore,
  CompositeFileStore,
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
