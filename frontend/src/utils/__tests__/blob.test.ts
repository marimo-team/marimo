/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, test } from "vitest";
import { deserializeBlob, serializeBlob } from "../blob";

describe("Blob serialization and deserialization", () => {
  const testString = "Hello, world!";
  const mimeType = "text/plain";
  let testBlob: Blob;

  beforeEach(() => {
    testBlob = new Blob([testString], { type: mimeType });
  });

  test("serializeBlob should serialize a Blob to a base64 string", async () => {
    const serialized = await serializeBlob(testBlob);
    expect(serialized).toBeDefined();
    expect(serialized).toContain(`data:${mimeType};base64,`);
  });

  test("deserializeBlob should deserialize a base64 string to a Blob", async () => {
    const serialized = await serializeBlob(testBlob);
    const deserialized = await deserializeBlob(serialized);
    expect(deserialized).toBeDefined();
    expect(deserialized.size).toBe(testBlob.size);
    expect(deserialized.type).toBe(testBlob.type);
  });

  test("deserialized Blob should contain the original content", async () => {
    const serialized = await serializeBlob(testBlob);
    const deserialized = await deserializeBlob(serialized);
    const reader = new FileReader();
    // eslint-disable-next-line unicorn/prefer-blob-reading-methods
    reader.readAsText(deserialized);
    await new Promise((resolve) => {
      reader.onload = () => {
        expect(reader.result).toBe(testString);
        resolve(null);
      };
    });
  });

  test("image Blobs should be deserialized correctly", async () => {
    const imageBlob = new Blob([new Uint8Array([1, 2, 3])], {
      type: "image/png",
    });
    const serialized = await serializeBlob(imageBlob);
    const deserialized = await deserializeBlob(serialized);
    expect(deserialized).toBeDefined();
    expect(deserialized.size).toBe(imageBlob.size);
    expect(deserialized.type).toBe(imageBlob.type);
  });
});
