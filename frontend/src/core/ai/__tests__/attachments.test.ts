/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import {
  getAttachmentMediaType,
  getSupportedAttachmentTypes,
  isSupportedAttachmentType,
} from "../attachments";

vi.mock("../model-registry", () => ({
  getKnownModelMaps: () => ({
    modelMap: new Map([
      ["openai/text-only", { input_types: ["text"] }],
      ["ollama/vision", { input_types: ["text", "image"] }],
      ["bedrock/multimodal", { input_types: ["text", "image", "pdf"] }],
      ["azure/unknown", { input_types: [] }],
    ]),
  }),
}));

describe("getSupportedAttachmentTypes", () => {
  it("allows text files for text-only models", () => {
    const types = getSupportedAttachmentTypes("openai/text-only");
    expect(types).toEqual(
      expect.arrayContaining([
        "text/*",
        "application/json",
        "application/toml",
        "application/yaml",
        "application/xml",
        ".toml",
        ".py",
        ".ipynb",
      ]),
    );
    expect(types).not.toContain("image/png");
    expect(types).not.toContain("application/pdf");
  });

  it("allows images for vision models on other providers", () => {
    expect(getSupportedAttachmentTypes("ollama/vision")).toEqual([
      ...getSupportedAttachmentTypes("openai/text-only"),
      "image/png",
      "image/jpeg",
      "image/gif",
      "image/webp",
    ]);
  });

  it("includes PDFs only when the model accepts them", () => {
    expect(getSupportedAttachmentTypes("bedrock/multimodal")).toContain(
      "application/pdf",
    );
    expect(getSupportedAttachmentTypes("ollama/vision")).not.toContain(
      "application/pdf",
    );
  });

  it.each(["custom/my-model", "openrouter/vendor/model", "azure/unknown"])(
    "allows supported file formats when metadata is unknown: %s",
    (model) => {
      expect(getSupportedAttachmentTypes(model)).toEqual(
        getSupportedAttachmentTypes("bedrock/multimodal"),
      );
    },
  );
});

describe("getAttachmentMediaType", () => {
  it.each([
    ["application/toml", "pyproject.toml"],
    ["application/yaml", "config.yaml"],
    ["application/x-yaml", "config.yml"],
    ["application/xml", "data.xml"],
    ["application/vnd.example+json", "data.json"],
    ["application/vnd.example+xml", "data.xml"],
    ["Text/Plain; charset=utf-8", "notes.txt"],
    ["", "script.PY"],
    ["application/octet-stream", "notebook.ipynb"],
  ])("normalizes %s for %s", (mediaType, filename) => {
    expect(getAttachmentMediaType(mediaType, filename)).toBe("text/plain");
  });

  it("does not treat a declared binary file as text based on its filename", () => {
    expect(getAttachmentMediaType("application/pdf", "misnamed.txt")).toBe(
      "application/pdf",
    );
  });
});

describe("isSupportedAttachmentType", () => {
  it.each([
    ["text/plain", true],
    ["text/markdown", true],
    ["application/json", true],
    ["image/png", false],
    ["application/pdf", false],
    ["application/octet-stream", false],
    ["", false],
  ])("checks %s against text-only inputs", (mediaType, expected) => {
    expect(
      isSupportedAttachmentType(
        mediaType,
        getSupportedAttachmentTypes("openai/text-only"),
      ),
    ).toBe(expected);
  });

  it("rejects unsupported image formats even for vision models", () => {
    expect(
      isSupportedAttachmentType(
        "image/svg+xml",
        getSupportedAttachmentTypes("ollama/vision"),
      ),
    ).toBe(false);
  });
});
