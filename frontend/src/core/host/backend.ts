/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookClient, NotebookTransport } from "@marimo-team/client";
import type { NotebookId } from "@marimo-team/client/protocol";

/** Events and commands for a notebook, independent of React or a replica. */
export interface NotebookBackend {
  readonly transport: NotebookTransport;
  /**
   * Commands for a notebook the transport reported.
   *
   * Method presence is not permission. The notebook advertises its operations.
   */
  notebook(id: NotebookId): Pick<NotebookClient, "edit">;
}
