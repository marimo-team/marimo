/* Copyright 2026 Marimo. All rights reserved. */

/** A notebook's events and commands, from a host or a stand-in for one. */

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
  /** Whether the host is reachable before an explicit reconnect. Absent means always. */
  checkHealth?(): Promise<boolean>;
}
