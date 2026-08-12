/* Copyright 2026 Marimo. All rights reserved. */
import type { OutputMessage } from "./kernel/messages";

export function isMarimoErrorsMime(
  mime: OutputMessage["mimetype"] | undefined,
) {
  return mime === "application/vnd.marimo+error";
}

export function isTracebackMime(mime: OutputMessage["mimetype"] | undefined) {
  return mime === "application/vnd.marimo+traceback";
}

export function isErrorMime(mime: OutputMessage["mimetype"] | undefined) {
  return isMarimoErrorsMime(mime) || isTracebackMime(mime);
}
