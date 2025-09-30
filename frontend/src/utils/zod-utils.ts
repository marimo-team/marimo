/* Copyright 2024 Marimo. All rights reserved. */

import z from "zod";

export function isZodArray<T>(
  schema: z.ZodType,
): schema is z.ZodArray<z.ZodType> {
  return schema instanceof z.ZodArray;
}

export function isZodPipe(schema: z.ZodType): schema is z.ZodPipe<z.ZodType> {
  return schema instanceof z.ZodPipe;
}

export function isZodTuple(
  schema: z.ZodType,
): schema is z.ZodTuple<z.ZodType[]> {
  return schema instanceof z.ZodTuple;
}
