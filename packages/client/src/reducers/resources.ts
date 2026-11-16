/* Copyright 2026 Marimo. All rights reserved. */

/** What a handler may know about the stream beyond the event. */
export interface HandlerContext {
  /** `snapshot` until `ready` arrives and `live` after it. */
  readonly phase: "snapshot" | "live";
}

/** Pure handlers for a resource's events. */
export interface EventResource<State, Event extends { event: string }> {
  readonly initial: State;
  readonly on: {
    readonly [Name in Event["event"]]?: (
      state: State,
      event: Extract<Event, { event: Name }>,
      context: HandlerContext,
    ) => State;
  };
}

/** Compose resource handlers without retaining their current state. */
export function composeResources<
  States extends object,
  Event extends { event: string },
>(resources: {
  readonly [Name in keyof States]: EventResource<States[Name], Event>;
}) {
  const names = Object.keys(resources) as (keyof States & string)[];
  const initial = Object.fromEntries(
    names.map((name) => [name, resources[name].initial]),
  ) as States;

  return {
    initial,
    reduce(state: States, event: Event, context: HandlerContext): States {
      let next = state;
      for (const name of names) {
        // The handler's key identifies the event it accepts.
        const handler = resources[name].on[event.event as Event["event"]] as
          | ((
              state: States[typeof name],
              event: Event,
              context: HandlerContext,
            ) => States[typeof name])
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
      return next;
    },
  };
}
