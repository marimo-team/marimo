/* Copyright 2026 Marimo. All rights reserved. */
import { z } from "zod";

const BufferPathSchema = z.array(z.array(z.union([z.string(), z.number()])));
const StateSchema = z.record(z.string(), z.any());

export const AnyWidgetMessageSchema = z.discriminatedUnion("method", [
  z.object({
    method: z.literal("open"),
    state: StateSchema,
    buffer_paths: BufferPathSchema.optional(),
  }),
  z.object({
    method: z.literal("update"),
    state: StateSchema,
    buffer_paths: BufferPathSchema.optional(),
  }),
  z.object({
    method: z.literal("custom"),
    content: z.any(),
  }),
  z.object({
    method: z.literal("echo_update"),
    buffer_paths: BufferPathSchema,
    state: StateSchema,
  }),
  z.object({
    method: z.literal("close"),
  }),
]);

export type AnyWidgetMessage = z.infer<typeof AnyWidgetMessageSchema>;
