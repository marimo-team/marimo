/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookEvent } from "./events";
import type * as Protocol from "./protocol";
import type {
  EventOf,
  Resource,
  ResourceEventName,
} from "./resources/resource";

/** A resource for each entry of a state map under the same name. */
export type Resources<States> = {
  readonly [Name in keyof States]: Resource<States[Name]>;
};

/**
 * The state of one notebook stream.
 *
 * Holds the phase, the notebook identity, and the state of each resource.
 */
export interface StreamState<States> {
  /** `snapshot` until `ready` arrives and `live` after it. */
  readonly phase: "snapshot" | "live";
  /**
   * The notebook the stream describes.
   *
   * Retained across `reset`.
   */
  readonly notebookId: Protocol.NotebookIdOutput | null;
  /** The state of each resource by name. */
  readonly resources: States;
}

/** A reducer over the events of one notebook stream. */
export interface Stream<States> {
  readonly initial: StreamState<States>;
  /**
   * Apply one event.
   *
   * Throws on a live event without a cursor or on an object from another
   * notebook.
   */
  reduce(state: StreamState<States>, event: NotebookEvent): StreamState<States>;
}

/** Events that may arrive without a cursor after `ready`. */
const UNCURSORED = new Set<NotebookEvent["event"]>([
  "reset",
  "marimo",
  "unknown",
]);

/**
 * The notebook the event's object belongs to.
 *
 * Undefined for objects that do not name one.
 */
function notebookIdOf(
  event: EventOf<ResourceEventName>,
): Protocol.NotebookIdOutput | undefined {
  switch (event.event) {
    case "document":
      return event.data.document.notebook_id;
    case "cell":
      return event.data.cell.notebook_id;
    case "analysis":
      return event.data.analysis.notebook_id;
    case "runtime":
      return event.data.runtime.notebook_id;
    case "attachment":
      return event.data.attachment.notebook_id;
    case "run":
      return event.data.run.notebook_id;
    default:
      return undefined;
  }
}

/** Compose resources into one stream. */
export function createStream<States extends object>(
  resources: Resources<States>,
): Stream<States> {
  const names = Object.keys(resources) as (keyof States & string)[];
  const initialResources = Object.fromEntries(
    names.map((name) => [name, resources[name].initial]),
  ) as States;
  const initial: StreamState<States> = {
    phase: "snapshot",
    notebookId: null,
    resources: initialResources,
  };

  function identify(
    state: StreamState<States>,
    notebookId: Protocol.NotebookIdOutput,
  ): StreamState<States> {
    if (state.notebookId === notebookId) {
      return state;
    }
    if (state.notebookId !== null) {
      throw new Error("Notebook stream changed identity");
    }
    return { ...state, notebookId };
  }

  function clear(state: StreamState<States>): StreamState<States> {
    return state.resources === initialResources
      ? state
      : { ...state, resources: initialResources };
  }

  function fanOut(
    state: StreamState<States>,
    event: EventOf<ResourceEventName>,
  ): StreamState<States> {
    let next = state.resources;
    for (const name of names) {
      type State = States[typeof name];
      // Handlers are keyed by the event name they accept.
      const handler = resources[name].on[event.event] as
        | ((state: State, event: Protocol.EventOutput) => State)
        | undefined;
      if (handler === undefined) {
        continue;
      }
      const before = next[name];
      const after = handler(before, event);
      if (after !== before) {
        next = { ...next, [name]: after };
      }
    }
    return next === state.resources ? state : { ...state, resources: next };
  }

  return {
    initial,
    reduce(state, event) {
      if (
        state.phase === "live" &&
        event.id === undefined &&
        !UNCURSORED.has(event.event)
      ) {
        throw new Error("Live notebook event is missing its cursor");
      }
      switch (event.event) {
        case "marimo":
        case "unknown":
          return state;
        case "reset":
          return { ...initial, notebookId: state.notebookId };
        case "ready":
          return state.phase === "live" ? state : { ...state, phase: "live" };
        case "notebook":
          return identify(state, event.data.notebook.id);
        case "notebook.removed":
          return state.notebookId !== null && event.data.id !== state.notebookId
            ? state
            : clear(state);
        default: {
          const notebookId = notebookIdOf(event);
          return fanOut(
            notebookId === undefined ? state : identify(state, notebookId),
            event,
          );
        }
      }
    },
  };
}
