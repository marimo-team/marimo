/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { getDefaults } from "@/components/forms/form-utils";

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

  it("should return default for ZodOptional with default", () => {
    const schema = z.object({
      foo: z.string().optional().default("bar"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ foo: "bar" });
  });

  it("should return undefined for ZodOptional without default", () => {
    const schema = z.object({
      foo: z.string().optional(),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ foo: undefined });
  });

  it("should return null for ZodNullable with nullish default", () => {
    const schema = z.object({
      foo: z.string().nullable().default(null),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ foo: null });
  });

  it("should handle nested objects with defaults", () => {
    const schema = z.object({
      outer: z.object({
        inner: z.string().default("baz"),
      }),
    });

    const result1 = getDefaults(schema);
    expect(result1).toEqual({ outer: undefined });

    const schema2 = schema.default({
      outer: {
        inner: "boo",
      },
    });
    const result2 = getDefaults(schema2);
    expect(result2).toEqual({ outer: { inner: "boo" } });
  });

  it("should handle ZodEnum with default", () => {
    const schema = z.object({
      color: z.enum(["red", "green", "blue"]).default("green"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ color: "green" });
  });

  it("should handle ZodUnion with default", () => {
    const schema = z.object({
      value: z.union([z.string(), z.number()]).default("foo"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ value: "foo" });
  });

  it("should handle ZodLiteral with default", () => {
    const schema = z.object({
      lit: z.literal("abc").default("abc"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ lit: "abc" });
  });

  it("should handle ZodDefault on ZodArray", () => {
    const schema = z.object({
      arr: z.array(z.number()).default([1, 2, 3]),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ arr: [1, 2, 3] });
  });

  it("should handle ZodRecord with default", () => {
    const schema = z.object({
      rec: z.record(z.string(), z.string()).default({ foo: "bar" }),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ rec: { foo: "bar" } });
  });

  it("should handle ZodMap with default", () => {
    const schema = z.object({
      map: z.map(z.string(), z.number()).default(new Map([["a", 1]])),
    });
    const result = getDefaults(schema);
    expect(result.map instanceof Map).toBe(true);
    expect([...result.map.entries()]).toEqual([["a", 1]]);
  });

  it("should handle ZodSet with default", () => {
    const schema = z.object({
      set: z.set(z.string()).default(new Set(["a", "b"])),
    });
    const result = getDefaults(schema);
    expect(result.set instanceof Set).toBe(true);
    expect([...result.set]).toEqual(["a", "b"]);
  });

  it("should handle deeply nested defaults", () => {
    const schema = z.object({
      a: z.object({
        b: z.object({
          c: z.string().default("deep"),
        }),
      }),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ a: undefined });
  });

  it("should handle ZodObject with no properties", () => {
    const schema = z.object({});
    const result = getDefaults(schema);
    expect(result).toEqual({});
  });

  it("should handle ZodTuple with defaults", () => {
    const schema = z.object({
      tup: z.tuple([z.string().default("a"), z.number().default(1)]),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ tup: ["a", 1] });
  });

  it("should handle ZodDefault on ZodObject", () => {
    const schema = z
      .object({
        foo: z.string(),
      })
      .default({ foo: "bar" });
    const result = getDefaults(schema);
    expect(result).toEqual({ foo: "bar" });
  });

  it("should handle ZodDefault on ZodString", () => {
    const schema = z.object({
      foo: z.string().default("bar"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ foo: "bar" });
  });

  it("should handle ZodDefault on ZodNumber", () => {
    const schema = z.object({
      num: z.number().default(42),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ num: 42 });
  });

  it("should handle ZodDefault on ZodBoolean", () => {
    const schema = z.object({
      flag: z.boolean().default(true),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ flag: true });
  });

  it("should handle ZodNullable with default", () => {
    const schema = z.object({
      maybe: z.string().nullable().default("x"),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ maybe: "x" });
  });

  it("should handle ZodOptional and ZodNullable with no default", () => {
    const schema = z.object({
      maybe: z.string().optional().nullable(),
    });
    const result = getDefaults(schema);
    expect(result).toEqual({ maybe: undefined });
  });
});
