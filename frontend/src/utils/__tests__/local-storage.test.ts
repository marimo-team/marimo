/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect, afterEach } from "vitest";
import { NotebookScopedLocalStorage } from "../localStorage";
import { z } from "zod";
import { store } from "@/core/state/jotai";
import { filenameAtom } from "@/core/saving/filenameAtom";

describe("NotebookScopedLocalStorage", () => {
  const schema = z.object({
    name: z.string(),
    age: z.number(),
  });

  const getDefaultValue = () => ({
    name: "John Doe",
    age: 30,
  });

  let storage: NotebookScopedLocalStorage<{
    name: string;
    age: number;
  }> | null;

  afterEach(() => {
    // Remove the storage after each test
    if (storage) {
      storage.dispose(); // Make sure to dispose the subscription
      storage.remove(KEY);
      storage = null;
    }
    // Reset atoms
    store.set(filenameAtom, null);
  });

  const KEY = "test";

  it("should initialize with the default value", () => {
    storage = new NotebookScopedLocalStorage(KEY, schema, getDefaultValue);
    expect(storage?.get(KEY)).toEqual(getDefaultValue());
  });

  it("should return default value after remove is called", () => {
    storage = new NotebookScopedLocalStorage(KEY, schema, getDefaultValue);
    // Set a custom value first
    storage.set(KEY, { name: "Jane Doe", age: 25 });
    expect(storage.get(KEY)).toEqual({ name: "Jane Doe", age: 25 });

    // Remove should clear the storage and return default value
    storage.remove(KEY);
    expect(storage.get(KEY)).toEqual(getDefaultValue());
  });

  it("should scope storage to filename when filename is set", async () => {
    // Set initial filename
    store.set(filenameAtom, "notebook.py");

    // Create storage with filename
    storage = new NotebookScopedLocalStorage(KEY, schema, getDefaultValue);
    expect(storage.createScopedKey(KEY, "notebook.py")).toEqual(
      "test:notebook.py",
    );

    // Set a value
    storage.set(KEY, { name: "Jane Doe", age: 25 });
    expect(storage.get(KEY)).toEqual({ name: "Jane Doe", age: 25 });

    // Change filename and verify key updates
    store.set(filenameAtom, "other.py");
    // Force a small delay to allow the subscription to process
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(storage.createScopedKey(KEY, "other.py")).toEqual("test:other.py");
    expect(storage.get(KEY)).toEqual({ name: "Jane Doe", age: 25 });
  });
});
