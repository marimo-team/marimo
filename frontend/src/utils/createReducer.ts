/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useSetAtom } from "jotai";
import type { Reducer } from "react";
import { Logger } from "@/utils/Logger";

type ReducerHandlers<State, Payloads> = {
  [Type in keyof Payloads]: (state: State, payload: Payloads[Type]) => State;
};

type ReducerConstraints<State> = Record<
  string,
  (state: State, payload: never) => State
>;

type PayloadsOf<RH> = {
  [Type in keyof RH]: RH[Type] extends (
    state: never,
    payload: infer Payload,
  ) => unknown
    ? Payload
    : never;
};

type Dispatch<Payloads> = (action: ReducerActionOf<Payloads>) => void;

type ReducerActions<Payloads> = {
  [Type in keyof Payloads]: unknown extends Payloads[Type]
    ? () => void
    : (payload: Payloads[Type]) => void;
};

/** Helper for typing middleware that receives dispatched actions. */
export type DispatchedActionOf<T> = {
  [Key in keyof T]: T[Key] extends (payload: infer P) => unknown
    ? { type: Key; payload: P }
    : never;
}[keyof T & string];

type ReducerActionOf<
  Payloads,
  Key extends keyof Payloads & string = keyof Payloads & string,
> = {
  [Type in Key]: { type: Type; payload: Payloads[Type] };
}[Key];

export interface ReducerCreatorResult<State, Payloads> {
  reducer: Reducer<State, ReducerActionOf<Payloads>>;
  createActions: (dispatch: Dispatch<Payloads>) => ReducerActions<Payloads>;
}

/**
 * Utility function to create a reducer and its actions.
 */
export function createReducer<
  State,
  RH extends ReducerConstraints<NoInfer<State>>,
>(
  initialState: () => State,
  reducers: RH & ReducerHandlers<NoInfer<State>, PayloadsOf<RH>>,
): ReducerCreatorResult<State, PayloadsOf<RH>> {
  type Payloads = PayloadsOf<RH>;
  const handlers: ReducerHandlers<State, Payloads> = reducers;
  return {
    reducer: (state, action) => {
      state = state || initialState();
      if (action.type in handlers) {
        return handlers[action.type](state, action.payload);
      }

      Logger.error(`Action type ${action.type} is not defined in reducers.`);
      return state;
    },
    createActions: (dispatch) => {
      const actions: {
        [Key in keyof Payloads]?: (payload: Payloads[Key]) => void;
      } = {};
      const addAction = <Key extends keyof Payloads & string>(type: Key) => {
        actions[type] = (payload) => dispatch({ type, payload });
      };
      for (const type in handlers) {
        addAction(type);
      }
      // The loop fills every key; payload-free creators receive undefined.
      return actions as ReducerActions<Payloads>;
    },
  };
}

type Middleware<State, Payloads> = (
  prevState: State,
  newState: State,
  action: ReducerActionOf<Payloads>,
) => void;

export function createReducerAndAtoms<
  State,
  RH extends ReducerConstraints<NoInfer<State>>,
>(
  initialState: () => State,
  reducers: RH & ReducerHandlers<NoInfer<State>, PayloadsOf<RH>>,
  middleware?: NoInfer<Middleware<State, PayloadsOf<RH>>[]>,
) {
  type Payloads = PayloadsOf<RH>;
  const allMiddleware = [...(middleware ?? [])];
  const addMiddleware = (mw: Middleware<State, Payloads>) => {
    allMiddleware.push(mw);
  };
  const { reducer, createActions } = createReducer<State, RH>(
    initialState,
    reducers,
  );

  const reduceSafely = (state: State, action: ReducerActionOf<Payloads>) => {
    try {
      return reducer(state, action);
    } catch (error) {
      Logger.error(`Error in reducer for action ${action.type}:`, error);
      return state;
    }
  };

  const runMiddleware = (
    prev: State,
    next: State,
    action: ReducerActionOf<Payloads>,
  ) => {
    for (const mw of allMiddleware) {
      try {
        mw(prev, next, action);
      } catch (error) {
        Logger.error(`Error in middleware for action ${action.type}:`, error);
      }
    }
  };

  const reducerWithMiddleware = (
    state: State,
    action: ReducerActionOf<Payloads>,
  ) => {
    const next = reduceSafely(state, action);
    runMiddleware(state, next, action);
    return next;
  };

  const valueAtom = atom(initialState());
  type ActionsCache = WeakMap<
    ReturnType<typeof useSetAtom<typeof valueAtom>>,
    ReducerActions<Payloads>
  >;
  const actionsMap: ActionsCache = new WeakMap();
  const plainActionsMap: ActionsCache = new WeakMap();

  function useActions(
    options: { skipMiddleware?: boolean } = {},
  ): ReducerActions<Payloads> {
    const setState = useSetAtom(valueAtom);
    const skipMiddleware = options.skipMiddleware === true;
    const cache = skipMiddleware ? plainActionsMap : actionsMap;

    const cachedActions = cache.get(setState);
    if (cachedActions) {
      return cachedActions;
    }
    const actions = createActions((action) => {
      // Middleware runs after the write commits so it observes the new state.
      let prev: State | undefined;
      let next: State | undefined;
      setState((state: State) => {
        prev = state;
        next = reduceSafely(state, action);
        return next;
      });
      if (!skipMiddleware && prev !== undefined && next !== undefined) {
        runMiddleware(prev, next, action);
      }
    });
    cache.set(setState, actions);
    return actions;
  }

  return {
    reducer: reducerWithMiddleware,
    addMiddleware,
    createActions,
    valueAtom,
    useActions,
  };
}
