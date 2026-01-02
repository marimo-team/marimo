/* Copyright 2026 Marimo. All rights reserved. */
import type { OutputMessage } from "./kernel/messages";

export function isErrorMime(mime: OutputMessage["mimetype"] | undefined) {
  return (
    mime === "application/vnd.marimo+error" ||
    mime === "application/vnd.marimo+traceback"
  );
}
