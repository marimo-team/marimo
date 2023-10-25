/* Copyright 2023 Marimo. All rights reserved. */

export function prettyError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}
