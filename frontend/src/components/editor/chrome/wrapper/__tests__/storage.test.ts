/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import { createStorage } from "../storage";

describe("createStorage", () => {
  beforeEach(() => {
    createStorage("left").setItem("test", "");
  });

  it("should store and retrieve items correctly when location is left", () => {
    const storage = createStorage("left");
    const value = JSON.stringify({ key: [1, 2] });

    storage.setItem("test", value);

    const retrieved = storage.getItem("test");
    expect(retrieved).toEqual(value);
  });

  it("should store and retrieve items correctly when location is bottom", () => {
    const storage = createStorage("bottom");
    const value = JSON.stringify({ key: [1, 2] });

    storage.setItem("test", value);

    const retrieved = storage.getItem("test");
    expect(retrieved).toEqual(value);
  });

  it("should return null when getting an item that does not exist", () => {
    const storage = createStorage("left");
    const retrieved = storage.getItem("nonexistent");
    expect(retrieved).toBeNull();
  });

  it("should return null when setting an item with invalid value", () => {
    const storage = createStorage("bottom");
    storage.setItem("test", "invalid");
    expect(storage.getItem("test")).toBeNull();
  });
});
