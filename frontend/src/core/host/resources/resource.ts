/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol";

/** An event name from the protocol. */
export type EventName = Protocol.EventOutput["event"];

/** The decoded event with the given name. */
export type EventOf<Name extends EventName> = Extract<
  Protocol.EventOutput,
  { event: Name }
>;

/**
 * Events the stream handles itself.
 *
 * They identify the notebook, discard state, or carry a native
 * notification. Resources do not receive them.
 */
export type StreamEventName =
  | "reset"
  | "notebook"
  | "notebook.removed"
  | "marimo";

/** Events a resource may handle. `ready` marks the end of the snapshot. */
export type ResourceEventName = Exclude<EventName, StreamEventName>;

/** `snapshot` until `ready` arrives and `live` after it. */
export type StreamPhase = "snapshot" | "live";

/** What a handler may know about the stream beyond the event. */
export interface HandlerContext {
  readonly phase: StreamPhase;
}

/**
 * A pure handler for each event the resource reads.
 *
 * A handler returns `state` when the event does not apply to it.
 */
export type EventHandlers<State> = {
  readonly [Name in ResourceEventName]?: (
    state: State,
    event: EventOf<Name>,
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
