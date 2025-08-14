import { describe, expect, it } from "vitest";

describe("JSON structure should be correct", async () => {
  it("should have the correct structure, models should be an object", async () => {
    const models = await import("../../data/generated/models.json");
    expect(Array.isArray(models.models)).toBe(true);
  });

  it("should have the correct structure, providers should be an object", async () => {
    const providers = await import("../../data/generated/providers.json");
    expect(Array.isArray(providers.providers)).toBe(true);
  });
});
