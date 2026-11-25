/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookResource } from "@marimo-team/client";
import type { AnalysisOutput as Analysis } from "@marimo-team/client/protocol";

export const analysis: NotebookResource<Analysis | null, "analysis"> = {
  initial: null,
  on: { analysis: (_state, { data }) => data.analysis },
};
