/* Copyright 2024 Marimo. All rights reserved. */
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";

export function getLSPDocument() {
  return `file://${getFilenameFromDOM() ?? "/__marimo_notebook__.py"}`;
}
