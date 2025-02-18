/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";

const DetailsSchema = z.object({
  detail: z.string(),
});

export function prettyError(error: unknown): string {
  if (!error) {
    return "Unknown error";
  }
  if (error instanceof Error) {
    const details = DetailsSchema.safeParse(error.cause);
    if (details.success) {
      return details.data.detail;
    }
    return maybeExtractDetails(error.message);
  }
  if (typeof error === "object") {
    const details = DetailsSchema.safeParse(error);
    if (details.success) {
      return details.data.detail;
    }
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function maybeExtractDetails(message: string): string {
  const parsed = safeJSONParse(message);
  if (!parsed) {
    return message;
  }
  const details = DetailsSchema.safeParse(parsed);
  if (details.success) {
    return details.data.detail;
  }
  return message;
}

function safeJSONParse(message: string): unknown {
  try {
    return JSON.parse(message);
  } catch {
    return message;
  }
}
