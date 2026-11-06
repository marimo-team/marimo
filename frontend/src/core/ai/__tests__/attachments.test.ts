/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import {
  getAttachmentMediaType,
  getSupportedAttachmentTypes,
  isSupportedAttachmentType,
  normalizeAttachment,
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
    expect(getSupportedAttachmentTypes("openai/text-only")).toEqual(["text/*"]);
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
    "application/toml",
    "application/yaml",
    "application/x-yaml",
    "application/xml",
    "application/vnd.example+json",
    "application/vnd.example+xml",
    "Text/Plain; charset=utf-8",
  ])("normalizes %s", (mediaType) => {
    expect(getAttachmentMediaType(mediaType)).toBe("text/plain");
  });

  it("does not treat a declared binary file as text based on its filename", () => {
    expect(getAttachmentMediaType("application/pdf")).toBe("application/pdf");
  });
});

describe("normalizeAttachment", () => {
  it.each([
    ["", "README"],
    ["application/octet-stream", "script.unlisted-extension"],
    ["application/javascript", "script.js"],
  ])("recognizes text by contents for %s, %s", async (type, name) => {
    const file = new File(["Hello, 世界!\n"], name, { type, lastModified: 42 });
    const normalized = await normalizeAttachment(file);
    expect({
      name: normalized.name,
      type: normalized.type,
      lastModified: normalized.lastModified,
      text: await normalized.text(),
    }).toEqual({
      name,
      type: "text/plain",
      lastModified: 42,
      text: "Hello, 世界!\n",
    });
  });

  it.each([
    new Uint8Array([0xff, 0xfe]),
    new Uint8Array([65, 0, 66]),
    new Uint8Array([65, 1, 66]),
  ])("preserves binary data despite a text filename", async (bytes) => {
    const file = new File([bytes], "script.py", {
      type: "application/octet-stream",
    });
    expect(await normalizeAttachment(file)).toBe(file);
  });

  it.each([
    "image/png",
    "image/svg+xml",
    "application/pdf",
    "audio/wav",
    "video/mp4",
  ])(
    "preserves declared %s files even if their contents are valid UTF-8",
    async (type) => {
      const file = new File(["ASCII payload"], "file.txt", { type });
      expect(await normalizeAttachment(file)).toBe(file);
    },
  );
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
        getAttachmentMediaType(mediaType),
        getSupportedAttachmentTypes("openai/text-only"),
      ),
    ).toBe(expected);
  });

  it("rejects unsupported image formats even for vision models", () => {
    expect(
      isSupportedAttachmentType(
        getAttachmentMediaType("image/svg+xml"),
        getSupportedAttachmentTypes("ollama/vision"),
      ),
    ).toBe(false);
  });
});
