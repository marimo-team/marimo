/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol";

/**
 * Events the stream handles itself.
 *
 * They identify the notebook, discard state, or carry a native
 * notification. Resources do not receive them.
 */
type StreamEventName = "reset" | "notebook" | "notebook.removed" | "marimo";

/** Events a resource may handle. `ready` marks the end of the snapshot. */
export type ResourceEvent = Exclude<
  Protocol.EventOutput,
  { event: StreamEventName }
>;

/** What a handler may know about the stream beyond the event. */
export interface HandlerContext {
  /** `snapshot` until `ready` arrives and `live` after it. */
  readonly phase: "snapshot" | "live";
}

/**
 * A pure handler for each event the resource reads.
 *
 * A handler returns `state` when the event does not apply to it.
 */
type EventHandlers<State> = {
  readonly [Name in ResourceEvent["event"]]?: (
    state: State,
    event: Extract<ResourceEvent, { event: Name }>,
    context: HandlerContext,
  ) => State;
};

/**
 * One kind of object assembled from its events.
 *
 * The stream returns a resource to `initial` on `reset` and when the
 * notebook is removed.
 */
export interface Resource<State> {
  readonly initial: State;
  readonly on: EventHandlers<State>;
}
