/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { getDefaults } from "@/plugins/impl/data-frames/forms/form-utils";
import { z } from "zod";

describe("getDefaults", () => {
  it("should return default value for ZodLiteral", () => {
    const schema = z.literal("default");
    const result = getDefaults(schema);
    expect(result).toBe("default");
  });

  it("should return default value for ZodDefault", () => {
    const schema = z.string().default("default");
    const result = getDefaults(schema);
    expect(result).toBe("default");
  });

  it("should return '' for ZodString without default and required", () => {
    const schema = z.string();
    const result = getDefaults(schema);
    expect(result).toBe("");
  });

  it("should return undefined for ZodString that is required", () => {
    expect(getDefaults(z.string().optional())).toBe(undefined);
    expect(getDefaults(z.string().nullish())).toBe(undefined);
    expect(getDefaults(z.optional(z.string()))).toBe(undefined);
  });

  it("should return enum value for ZodEnum", () => {
    const schema = z.enum(["default", "other"]);
    const result = getDefaults(schema);
    expect(result).toBe("default");
  });

  it("should return undefined for optional ZodEnum", () => {
    const schema = z.enum(["default", "other"]).optional();
    const result = getDefaults(schema);
    expect(result).toBe(undefined);
  });

  it("should return default value for the first option in ZodUnion", () => {
    const schema = z.union([z.literal("default"), z.string()]);
    const result = getDefaults(schema);
    expect(result).toBe("default");
  });

  it("should return default values for ZodObject", () => {
    const schema = z.object({
      string: z.string().default("default"),
      number: z.number().default(123),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({
      string: "default",
      number: 123,
    });
  });

  it("should return undefined for ZodObject properties without default", () => {
    const schema = z.object({
      string: z.string(),
      number: z.number(),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({
      string: undefined,
      number: undefined,
    });
  });

  it("should return default values for ZodObject and refine", () => {
    const schema = z.object({
      string: z.string().default("foo"),
      number: z.number().default(123),
    });
    const result = getDefaults(schema.refine((v) => v.string === "bar"));
    expect(result).toEqual({
      string: "foo",
      number: 123,
    });
  });

  it("should return default values for ZodArray", () => {
    const schema = z.array(
      z.object({
        string: z.string().default("default"),
        number: z.number().default(123),
      }),
    );
    const result = getDefaults(schema);
    expect(result).toEqual([]);

    const schema2 = schema.min(1);
    const result2 = getDefaults(schema2);
    expect(result2).toEqual([
      {
        string: "default",
        number: 123,
      },
    ]);
  });
});
