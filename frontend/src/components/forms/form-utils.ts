/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { Logger } from "@/utils/Logger";
import { isZodArray, isZodPipe, isZodTuple } from "@/utils/zod-utils";

export function maybeUnwrap<T extends z.ZodType>(schema: T): z.ZodType {
  if ("unwrap" in schema) {
    return (schema as unknown as z.ZodOptional).unwrap() as z.ZodType;
  }
  return schema;
}

/**
 * Get default values for a zod schema
 */
export function getDefaults<TSchema extends z.ZodType<T>, T>(
  schema: TSchema,
): T {
  const getDefaultValue = (schema: z.ZodType): unknown => {
    if (schema instanceof z.ZodLiteral) {
      const values = [...schema.values];
      if (schema.values.size === 1) {
        return values[0];
      }
      return values;
    }
    if (schema instanceof z.ZodDefault) {
      const defValue = schema.def.defaultValue;
      return typeof defValue === "function" ? defValue() : defValue;
    }
    if (isZodPipe(schema)) {
      return getDefaultValue(schema.in);
    }
    if (isZodTuple(schema)) {
      return schema.def.items.map((item) => getDefaultValue(item));
    }
    if ("unwrap" in schema) {
      return getDefaultValue(maybeUnwrap(schema));
    }
    return undefined;
  };

  // If union, take the first one
  if (
    schema instanceof z.ZodUnion ||
    schema instanceof z.ZodDiscriminatedUnion
  ) {
    return getDefaultValue(schema.options[0] as z.ZodType) as T;
  }

  // If array, return an array of 1 item
  if (isZodArray(schema)) {
    if (doesArrayRequireMinLength(schema)) {
      return [getDefaults(schema.element)] as T;
    }
    return [] as T;
  }

  // If string, return the default value
  if (schema instanceof z.ZodString) {
    return "" as T;
  }

  // If enum, return the first value
  if (schema instanceof z.ZodEnum) {
    const values = schema.options;
    return values[0] as T;
  }

  // If not an object, return the default value
  if (!(schema instanceof z.ZodObject)) {
    return getDefaultValue(schema) as T;
  }

  return Object.fromEntries(
    Object.entries(schema.shape).map(([key, value]: [string, z.ZodType]) => {
      return [key, getDefaultValue(value)];
    }),
  ) as T;
}

/**
 * Get the literal value of a union
 */
export function getUnionLiteral<T extends z.ZodType>(
  schema: T,
): z.ZodLiteral<string> {
  if (schema instanceof z.ZodLiteral) {
    return schema as z.ZodLiteral<string>;
  }
  if (schema instanceof z.ZodObject) {
    const typeField = schema.shape.type;
    if (typeField instanceof z.ZodLiteral) {
      return typeField as z.ZodLiteral<string>;
    }
    throw new Error("Invalid schema");
  }
  if (
    schema instanceof z.ZodUnion ||
    schema instanceof z.ZodDiscriminatedUnion
  ) {
    return getUnionLiteral(schema.options[0] as z.ZodType);
  }
  Logger.warn(schema);
  throw new Error("Invalid schema");
}

function doesArrayRequireMinLength<T extends z.ZodArray>(schema: T): boolean {
  const result = schema.safeParse([]);
  if (!result.success) {
    return true;
  }
  return false;
}
