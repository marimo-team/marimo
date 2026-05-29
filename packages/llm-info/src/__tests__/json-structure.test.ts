import { describe, expect, it } from "vitest";

describe("JSON structure should be correct", async () => {
  it("models.json wraps a provider-keyed map under `models`", async () => {
    const models = await import("../../data/generated/models.json");
    expect(typeof models.models).toBe("object");
    expect(Array.isArray(models.models)).toBe(false);
    for (const [, list] of Object.entries(
      models.models as Record<string, unknown>,
    )) {
      expect(Array.isArray(list)).toBe(true);
    }
  });

  it("providers.json wraps an array under `providers`", async () => {
    const providers = await import("../../data/generated/providers.json");
    expect(Array.isArray(providers.providers)).toBe(true);
  });
});
