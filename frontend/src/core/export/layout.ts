/* Copyright 2026 Marimo. All rights reserved. */

import { flushDocumentChanges } from "@/core/cells/document-changes";
import { getSerializedLayout } from "@/core/layout/layout";

export async function getExportLayout() {
  await flushDocumentChanges();
  return getSerializedLayout();
}
