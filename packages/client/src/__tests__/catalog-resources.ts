/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookOutput, ProjectOutput } from "../protocol.ts";
import type { CatalogResource } from "../index.ts";

/** An example application keeps just the records it uses. */
export const notebooks: CatalogResource<readonly NotebookOutput[], "notebook"> =
  {
    initial: [],
    on: {
      notebook: (state, { data }) => [
        ...state.filter((entry) => entry.id !== data.notebook.id),
        data.notebook,
      ],
      "notebook.removed": (state, { data }) =>
        state.filter((entry) => entry.id !== data.id),
    },
  };

export const projects: CatalogResource<readonly ProjectOutput[], "project"> = {
  initial: [],
  on: {
    project: (state, { data }) => [
      ...state.filter((entry) => entry.id !== data.project.id),
      data.project,
    ],
  },
};
