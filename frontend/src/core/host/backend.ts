/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookClient, NotebookTransport } from "@marimo-team/client";

/** Events and commands for the same notebook, independent of React or a replica. */
export interface NotebookBackend {
  readonly transport: NotebookTransport;
  /** Method presence is not permission; the notebook advertises its operations. */
  readonly client: Pick<NotebookClient, "edit">;
}
