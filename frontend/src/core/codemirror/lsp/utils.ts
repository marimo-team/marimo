/* Copyright 2024 Marimo. All rights reserved. */
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { Paths } from "@/utils/paths";

export function getLSPDocument() {
  return `file://${getFilenameFromDOM() ?? "/__marimo_notebook__.py"}`;
}

export function getLSPDocumentRootUri() {
  return `file://${Paths.dirname(getFilenameFromDOM() ?? "/")}`;
}
