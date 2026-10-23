/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "../protocol.ts";
import type { NotebookKind } from "../kinds.ts";
import {
  composeResources,
  type EventResource,
  type HandlerContext,
} from "./resources.ts";

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
export type NotebookResourceEvent<K extends NotebookKind = NotebookKind> =
  Extract<
    Exclude<Protocol.EventOutput, { event: ControlName }>,
    { event: K | `${K}.removed` | "ready" }
  >;

/**
 * One kind of object assembled from its events.
 *
 * The reducer returns a resource to `initial` on `reset` and when the
 * notebook is removed.
 */
export interface NotebookResource<
  State,
  K extends NotebookKind = NotebookKind,
> extends EventResource<State, NotebookResourceEvent<K>> {}

/** The state of one notebook stream. */
export interface NotebookReducerState<States> {
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
export interface NotebookReducer<States> {
  readonly initial: NotebookReducerState<States>;
  /**
   * Apply one event.
   *
   * Throws on an object from another notebook.
   */
  reduce(
    state: NotebookReducerState<States>,
    event: Protocol.EventOutput,
  ): NotebookReducerState<States>;
}

/** A resource for each entry of a state map under the same name. */
type Resources<States> = {
  readonly [Name in keyof States]: NotebookResource<States[Name]>;
};

/**
 * The notebook the event's object belongs to.
 *
 * Undefined for objects that do not name one.
 */
function notebookIdOf(
  event: NotebookResourceEvent,
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
export function createNotebookReducer<States extends object>(
  resources: Resources<States>,
): NotebookReducer<States> {
  const handlers = composeResources<States, NotebookResourceEvent>(resources);
  const initialResources = handlers.initial;
  const initial: NotebookReducerState<States> = {
    phase: "snapshot",
    notebookId: null,
    notebook: null,
    resources: initialResources,
  };

  function identify(
    state: NotebookReducerState<States>,
    notebookId: Protocol.NotebookIdOutput,
  ): NotebookReducerState<States> {
    if (state.notebookId === notebookId) {
      return state;
    }
    if (state.notebookId !== null) {
      throw new Error("Notebook stream changed identity");
    }
    return { ...state, notebookId };
  }

  function clear(
    state: NotebookReducerState<States>,
  ): NotebookReducerState<States> {
    return state.resources === initialResources && state.notebook === null
      ? state
      : { ...state, notebook: null, resources: initialResources };
  }

  function fanOut(
    state: NotebookReducerState<States>,
    event: NotebookResourceEvent,
  ): NotebookReducerState<States> {
    const next = handlers.reduce(state.resources, event, {
      phase: state.phase,
    });
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
