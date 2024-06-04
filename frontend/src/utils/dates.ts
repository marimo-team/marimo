/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "./Logger";

export function prettyDate(value: string | number | null | undefined): string {
  if (value == null) {
    return "";
  }

  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (error) {
    Logger.warn("Failed to parse date", error);
    return value.toString();
  }
}
