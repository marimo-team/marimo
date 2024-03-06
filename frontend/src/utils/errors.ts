/* Copyright 2024 Marimo. All rights reserved. */

export function prettyError(error: unknown): string {
  if (!error) {
    return "Unknown error";
  }
  if (error instanceof Error) {
    return maybeExtractDetails(error.message);
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function maybeExtractDetails(message: string): string {
  try {
    const parsed = JSON.parse(message);
    if (!parsed) {
      return message;
    }
    if (
      typeof parsed === "object" &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
    ) {
      return parsed.detail;
    }
  } catch {
    // noop
  }
  return message;
}
