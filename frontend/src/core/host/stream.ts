/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookEvent } from "./events";
import type * as Protocol from "./protocol";
import type {
  EventOf,
  HandlerContext,
  Resource,
  ResourceEventName,
  StreamPhase,
} from "./resources/resource";

/** A resource for each entry of a state map under the same name. */
export type Resources<States> = {
  readonly [Name in keyof States]: Resource<States[Name]>;
};

/**
 * The state of one notebook stream.
 *
 * Holds the phase, the notebook identity, the resume cursor, and the state
 * of each resource.
 */
export interface StreamState<States> {
  readonly phase: StreamPhase;
  /**
   * The notebook the stream describes.
   *
   * Retained across `reset`.
   */
  readonly notebookId: Protocol.NotebookIdOutput | null;
  /**
   * The id of the last live event.
   *
   * Null before `ready` and after `reset`.
   */
  readonly cursor: string | null;
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
  /**
   * The state to hold while reconnecting.
   *
   * A live stream keeps its state and resumes from `cursor`. An incomplete
   * snapshot starts over.
   */
  resume(state: StreamState<States>): StreamState<States>;
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
    cursor: null,
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
    const context: HandlerContext = { phase: state.phase };
    let next = state.resources;
    for (const name of names) {
      type State = States[typeof name];
      // Handlers are keyed by the event name they accept.
      const handler = resources[name].on[event.event] as
        | ((
            state: State,
            event: Protocol.EventOutput,
            context: HandlerContext,
          ) => State)
        | undefined;
      if (handler === undefined) {
        continue;
      }
      const before = next[name];
      const after = handler(before, event, context);
      if (after !== before) {
        next = { ...next, [name]: after };
      }
    }
    return next === state.resources ? state : { ...state, resources: next };
  }

  /** Record the position of a live event. */
  function advance(
    state: StreamState<States>,
    id: string | undefined,
  ): StreamState<States> {
    return state.phase === "live" && id !== undefined && id !== state.cursor
      ? { ...state, cursor: id }
      : state;
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
          return advance(state, event.id);
        case "reset":
          return { ...initial, notebookId: state.notebookId };
        case "ready":
          // Handlers see the phase that ended, so a snapshot's ready differs
          // from one that ends a replay.
          return { ...fanOut(state, event), phase: "live", cursor: event.id };
        case "notebook":
          return advance(identify(state, event.data.notebook.id), event.id);
        case "notebook.removed":
          return advance(
            state.notebookId !== null && event.data.id !== state.notebookId
              ? state
              : clear(state),
            event.id,
          );
        default: {
          const notebookId = notebookIdOf(event);
          return advance(
            fanOut(
              notebookId === undefined ? state : identify(state, notebookId),
              event,
            ),
            event.id,
          );
        }
      }
    },
    resume(state) {
      return state.phase === "snapshot"
        ? { ...initial, notebookId: state.notebookId }
        : state;
    },
  };
}
