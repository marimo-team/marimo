/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

/**
 * Get default values for a zod schema
 */
export function getDefaults<TSchema extends z.ZodType<T>, T>(
  schema: TSchema,
): T {
  const getDefaultValue = (schema: z.ZodTypeAny): unknown => {
    if (schema instanceof z.ZodLiteral) {
      return schema._def.value;
    }
    if (schema instanceof z.ZodDefault) {
      return schema._def.defaultValue();
    }
    if (schema instanceof z.ZodEffects) {
      return getDefaults(schema._def.schema);
    }
    if (!("innerType" in schema._def)) {
      return undefined;
    }
    return getDefaultValue(schema._def.innerType);
  };

  // If union, take the first one
  if (schema instanceof z.ZodUnion) {
    return getDefaultValue(schema._def.options[0]) as T;
  }

  // If array, return an array of 1 item
  if (schema instanceof z.ZodArray) {
    if (schema._def.minLength && schema._def.minLength.value > 0) {
      return [getDefaults(schema._def.type)] as unknown as T;
    }
    return [] as unknown as T;
  }

  // If string, return the default value
  if (schema instanceof z.ZodString) {
    return "" as T;
  }

  // If enum, return the first value
  if (schema instanceof z.ZodEnum) {
    return schema._def.values[0] as T;
  }

  // If not an object, return the default value
  if (!(schema instanceof z.ZodObject)) {
    return getDefaultValue(schema) as T;
  }

  return Object.fromEntries(
    Object.entries(schema.shape).map(([key, value]) => {
      return [key, getDefaultValue(value as z.AnyZodObject)];
    }),
  ) as T;
}

/**
 * Get the literal value of a union
 */
export function getUnionLiteral<T extends z.ZodType<unknown>>(
  schema: T,
): z.ZodLiteral<string> {
  if (schema instanceof z.ZodLiteral) {
    return schema;
  }
  if (schema instanceof z.ZodObject) {
    const type = schema._def.shape().type;
    if (type instanceof z.ZodLiteral) {
      return type;
    }
    throw new Error("Invalid schema");
  }
  if (schema instanceof z.ZodUnion) {
    return getUnionLiteral(schema._def.options[0]);
  }
  throw new Error("Invalid schema");
}
