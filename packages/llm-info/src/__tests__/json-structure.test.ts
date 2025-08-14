import { describe, expect, it } from "vitest";

describe("JSON structure should be correct", async () => {
  it("should have the correct structure, models.models should be an object", async () => {
    const models = await import("../../data/generated/models.json");
    expect(typeof models.models).toBe("object");
  });

  it("should have the correct structure, providers.providers should be an object", async () => {
    const providers = await import("../../data/generated/providers.json");
    expect(typeof providers.providers).toBe("object");
  });
});
