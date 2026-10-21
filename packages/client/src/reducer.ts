/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "./protocol.ts";

/** A kind of object a notebook stream carries. */
export type Kind = Exclude<Protocol.ObjectTypeOutput, "host" | "project">;

/**
 * Events the reducer handles itself.
 *
 * They identify the notebook or discard state. Resources do not receive them.
 */
type ControlName = "reset" | "notebook" | "notebook.removed";

/**
 * The events a resource may handle for some kinds.
 *
 * Each kind contributes its record and removal events. `ready` marks the end
 * of the snapshot and belongs to every kind.
 */
export type ResourceEvent<K extends Kind = Kind> = Extract<
  Exclude<Protocol.EventOutput, { event: ControlName }>,
  { event: K | `${K}.removed` | "ready" }
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
type EventHandlers<State, K extends Kind> = {
  readonly [Name in ResourceEvent<K>["event"]]?: (
    state: State,
    event: Extract<ResourceEvent<K>, { event: Name }>,
    context: HandlerContext,
  ) => State;
};

/**
 * One kind of object assembled from its events.
 *
 * The reducer returns a resource to `initial` on `reset` and when the
 * notebook is removed.
 */
export interface Resource<State, K extends Kind = Kind> {
  readonly initial: State;
  readonly on: EventHandlers<State, K>;
}

/** The state of one notebook stream. */
export interface ReducerState<States> {
  readonly phase: HandlerContext["phase"];
  /**
   * The notebook the stream describes.
   *
   * Cleared on `reset`: session brokering may select a new notebook.
   */
  readonly notebookId: Protocol.NotebookIdOutput | null;
  /** Latest notebook metadata, cleared on reset or removal. */
  readonly notebook: Protocol.NotebookOutput | null;
  /** The state of each resource by name. */
  readonly resources: States;
}

/** A pure reducer over the events of one notebook stream. */
export interface Reducer<States> {
  readonly initial: ReducerState<States>;
  /**
   * Apply one event.
   *
   * Throws on an object from another notebook.
   */
  reduce(
    state: ReducerState<States>,
    event: Protocol.EventOutput,
  ): ReducerState<States>;
}

/** A resource for each entry of a state map under the same name. */
type Resources<States> = {
  readonly [Name in keyof States]: Resource<States[Name]>;
};

/**
 * The notebook the event's object belongs to.
 *
 * Undefined for objects that do not name one.
 */
function notebookIdOf(
  event: ResourceEvent,
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

/** Compose resources into one reducer over a notebook stream. */
export function createReducer<States extends object>(
  resources: Resources<States>,
): Reducer<States> {
  const names = Object.keys(resources) as (keyof States & string)[];
  const initialResources = Object.fromEntries(
    names.map((name) => [name, resources[name].initial]),
  ) as States;
  const initial: ReducerState<States> = {
    phase: "snapshot",
    notebookId: null,
    notebook: null,
    resources: initialResources,
  };

  function identify(
    state: ReducerState<States>,
    notebookId: Protocol.NotebookIdOutput,
  ): ReducerState<States> {
    if (state.notebookId === notebookId) {
      return state;
    }
    if (state.notebookId !== null) {
      throw new Error("Notebook stream changed identity");
    }
    return { ...state, notebookId };
  }

  function clear(state: ReducerState<States>): ReducerState<States> {
    return state.resources === initialResources && state.notebook === null
      ? state
      : { ...state, notebook: null, resources: initialResources };
  }

  function fanOut(
    state: ReducerState<States>,
    event: ResourceEvent,
  ): ReducerState<States> {
    const context: HandlerContext = { phase: state.phase };
    let next = state.resources;
    for (const name of names) {
      type State = States[typeof name];
      // Handlers are keyed by the event name they accept.
      const handler = resources[name].on[event.event] as
        | ((
            state: State,
            event: ResourceEvent,
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

  return {
    initial,
    reduce(state, event) {
      switch (event.event) {
        case "reset":
          return initial;
        case "ready":
          // Handlers see the phase that ended, so a snapshot's ready differs
          // from one that ends a replay.
          return { ...fanOut(state, event), phase: "live" };
        case "notebook":
          return {
            ...identify(state, event.data.notebook.id),
            notebook: event.data.notebook,
          };
        case "host":
        case "project":
        case "project.removed":
          // The catalog's kinds do not appear on a notebook stream.
          return state;
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
