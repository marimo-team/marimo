import z from "zod";

export function isZodArray<T>(
  schema: z.ZodType<unknown>,
): schema is z.ZodArray<z.ZodType<unknown>> {
  return schema instanceof z.ZodArray;
}

export function isZodPipe(
  schema: z.ZodType<unknown>,
): schema is z.ZodPipe<z.ZodType<unknown>> {
  return schema instanceof z.ZodPipe;
}

export function isZodTuple(
  schema: z.ZodType<unknown>,
): schema is z.ZodTuple<z.ZodType<unknown>[]> {
  return schema instanceof z.ZodTuple;
}
