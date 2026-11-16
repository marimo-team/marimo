/* Copyright 2026 Marimo. All rights reserved. */

import type { Runtime } from "@marimo-team/client/protocol";
import type { NotebookResource } from "@marimo-team/client";

/** The notebook's runtime record while it has one. */
export const runtime: NotebookResource<Runtime | null, "runtime"> = {
  initial: null,
  on: {
    runtime: (_state, { data }) => data.runtime,
    "runtime.removed": (state, { data }) =>
      state !== null && state.id === data.id ? null : state,
  },
};
