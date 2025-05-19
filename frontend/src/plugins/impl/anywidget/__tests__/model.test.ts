/* Copyright 2024 Marimo. All rights reserved. */
import { describe, beforeEach, it, expect, vi } from "vitest";
import {
  Model,
  handleWidgetMessage,
  type AnyWidgetMessage,
  visibleForTesting,
} from "../model";
import type { Base64String } from "@/utils/json/base64";

const { ModelManager } = visibleForTesting;

describe("ModelManager", () => {
  let modelManager = new ModelManager(50);
  const handle = (
    modelId: string,
    message: AnyWidgetMessage,
    buffers: Base64String[],
  ) => {
    return handleWidgetMessage(modelId, message, buffers, modelManager);
  };

  beforeEach(() => {
    // Clear the model manager before each test
    modelManager = new ModelManager(50);
  });

  it("should set and get models", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);
    const retrievedModel = await modelManager.get("test-id");
    expect(retrievedModel).toBe(model);
  });

  it("should handle model not found", async () => {
    await expect(modelManager.get("non-existent")).rejects.toThrow(
      "Model not found for key: non-existent",
    );
  });

  it("should delete models", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);
    modelManager.delete("test-id");
    await expect(modelManager.get("test-id")).rejects.toThrow();
  });

  it("should handle widget messages", async () => {
    const openMessage: AnyWidgetMessage = {
      method: "open",
      state: { count: 0 },
      buffer_paths: [],
    };

    await handle("test-id", openMessage, []);
    const model = await modelManager.get("test-id");
    expect(model.get("count")).toBe(0);

    const updateMessage: AnyWidgetMessage = {
      method: "update",
      state: { count: 1 },
      buffer_paths: [],
    };

    await handle("test-id", updateMessage, []);
    expect(model.get("count")).toBe(1);
  });

  it("should handle close messages", async () => {
    const model = new Model({ count: 0 }, vi.fn(), vi.fn(), new Set());
    modelManager.set("test-id", model);

    await handle("test-id", { method: "close" }, []);
    await expect(modelManager.get("test-id")).rejects.toThrow();
  });
});
