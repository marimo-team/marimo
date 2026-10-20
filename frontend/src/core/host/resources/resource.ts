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
 * They mark the phase, identify the notebook, or carry a native
 * notification. Resources do not receive them.
 */
export type StreamEventName =
  | "reset"
  | "ready"
  | "notebook"
  | "notebook.removed"
  | "marimo";

/** Events a resource may handle. */
export type ResourceEventName = Exclude<EventName, StreamEventName>;

/**
 * A pure handler for each event the resource reads.
 *
 * A handler returns `state` when the event does not apply to it.
 */
export type EventHandlers<State> = {
  readonly [Name in ResourceEventName]?: (
    state: State,
    event: EventOf<Name>,
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
