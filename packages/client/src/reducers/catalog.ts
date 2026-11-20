/* Copyright 2026 Marimo. All rights reserved. */

import type { CatalogEvent } from "../catalog/events.ts";
import type { CatalogKind } from "../kinds.ts";
import {
  composeResources,
  type EventResource,
  type HandlerContext,
} from "./resources.ts";

/** Catalog records, removals, and the end of a snapshot or replay. */
export type CatalogResourceEvent<K extends CatalogKind = CatalogKind> = Exclude<
  CatalogEvent<K>,
  { event: "reset" }
>;

/** Pure catalog handlers. A reset returns every resource to its initial state. */
export interface CatalogResource<
  State,
  K extends CatalogKind = CatalogKind,
> extends EventResource<State, CatalogResourceEvent<K>> {}

/** The caller's state for a catalog stream. */
export interface CatalogReducerState<States> {
  readonly phase: HandlerContext["phase"];
  readonly resources: States;
}

/** A pure reducer over the events of a catalog stream. */
export interface CatalogReducer<States> {
  readonly initial: CatalogReducerState<States>;
  reduce(
    state: CatalogReducerState<States>,
    event: CatalogEvent,
  ): CatalogReducerState<States>;
}

/** Compose resources into a catalog reducer. The caller owns and updates state. */
export function createCatalogReducer<States extends object>(resources: {
  readonly [Name in keyof States]: CatalogResource<States[Name]>;
}): CatalogReducer<States> {
  const handlers = composeResources<States, CatalogResourceEvent>(resources);
  const initial: CatalogReducerState<States> = {
    phase: "snapshot",
    resources: handlers.initial,
  };
  return {
    initial,
    reduce(state, event) {
      if (event.event === "reset") {
        return initial;
      }
      const next = handlers.reduce(state.resources, event, {
        phase: state.phase,
      });
      const phase = event.event === "ready" ? "live" : state.phase;
      return next === state.resources && phase === state.phase
        ? state
        : { phase, resources: next };
    },
  };
}
