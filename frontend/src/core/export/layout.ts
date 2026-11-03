/* Copyright 2026 Marimo. All rights reserved. */

import { flushDocument } from "@/core/cells/document";
import { getSerializedLayout } from "@/core/layout/layout";

export async function getExportLayout() {
  await flushDocument();
  return getSerializedLayout();
}
