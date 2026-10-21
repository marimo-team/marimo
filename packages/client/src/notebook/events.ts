/* Copyright 2026 Marimo. All rights reserved. */

import { type NotebookKind, notebookKinds } from "../kinds.ts";
import type * as Protocol from "../protocol.ts";
import { Events, type EventsInit } from "../transport/events.ts";
import type { NotebookTransport } from "../transport/frame.ts";
import type { StreamEvent } from "../transport/stream.ts";

/** An event delivered for the requested notebook kinds, plus ready and reset. */
export type NotebookEvent<K extends string = NotebookKind> = StreamEvent<K>;

/** How a notebook stream reaches its host and what it follows. */
export interface NotebookEventsInit<
  K extends string = NotebookKind,
> extends EventsInit<K> {
  /** Follow one run. A custom transport filters its own requests. */
  readonly runId?: Protocol.RunId;
}

/**
 * A notebook stream, followed across reconnects.
 *
 * Starts with a snapshot ending in `ready`, then delivers changes. A dropped
 * connection resumes from its cursor. On `reset`, discard accumulated state
 * before applying the fresh snapshot. A custom transport may replace SSE.
 */
export class NotebookEvents<
  const K extends string = NotebookKind,
> extends Events<K> {
  public constructor(
    source: string | URL | NotebookTransport,
    init: NotebookEventsInit<K> = {},
  ) {
    if (typeof source !== "function" && init.runId !== undefined) {
      source = new URL(source);
      source.searchParams.set("run_id", init.runId);
    }
    super(source, init, notebookKinds);
  }
}
