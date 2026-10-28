/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import { atom, useSetAtom } from "jotai";
import type { Reducer } from "react";
import { Logger } from "@/utils/Logger";

export type NoInfer<T> = [T][T extends any ? 0 : never];

type Dispatch<RH> = (action: ReducerActionOf<RH>) => void;
type IfUnknown<T, Y, N> = unknown extends T ? Y : N;

type ReducerHandler<State, Payload> = (state: State, payload: Payload) => State;

interface ReducerHandlers<State> {
  [k: string]: ReducerHandler<State, any>;
}

type ReducerActions<RH extends ReducerHandlers<any>> = {
  [Type in keyof RH]: RH[Type] extends ReducerHandler<any, infer Payload>
    ? IfUnknown<Payload, () => void, (payload: Payload) => void>
    : never;
};

/** Helper for typing middleware that receives dispatched actions. */
export type DispatchedActionOf<T> = {
  [Key in keyof T]: T[Key] extends (payload: infer P) => any
    ? { type: Key; payload: P }
    : never;
}[keyof T & string];

type ReducerActionOf<RH> = {
  [Type in keyof RH]: RH[Type] extends ReducerHandler<any, infer Payload>
    ? { type: Type; payload: Payload }
    : never;
}[keyof RH & string];

export interface ReducerCreatorResult<
  State,
  RH extends ReducerHandlers<State>,
> {
  /**
   * The reducer function.
   */
  reducer: Reducer<State, any>;
  /**
   * Given a dispatch function, returns an object containing all the actions.
   */
  createActions: (dispatch: Dispatch<RH>) => ReducerActions<RH>;
}

/**
 * Utility function to create a reducer and its actions.
 */
export function createReducer<
  State,
  RH extends ReducerHandlers<NoInfer<State>>,
>(initialState: () => State, reducers: RH): ReducerCreatorResult<State, RH> {
  return {
    reducer: (state, action: ReducerActionOf<RH>) => {
      state = state || initialState();
      if (action.type in reducers) {
        return reducers[action.type](state, action.payload);
      }

      Logger.error(`Action type ${action.type} is not defined in reducers.`);
      return state;
    },
    createActions: (dispatch: Dispatch<RH>) => {
      const actions = {} as ReducerActions<RH>;
      for (const type in reducers) {
        (actions as any)[type] = (payload: any) => {
          dispatch({ type, payload } as any);
        };
      }
      return actions;
    },
  };
}

type Middleware<State, RH> = (
  prevState: State,
  newState: State,
  action: ReducerActionOf<RH>,
) => void;

export function createReducerAndAtoms<
  State,
  RH extends ReducerHandlers<NoInfer<State>>,
>(
  initialState: () => State,
  reducers: RH,
  middleware?: Middleware<State, NoInfer<RH>>[],
) {
  const allMiddleware = [...(middleware ?? [])];
  const addMiddleware = (mw: Middleware<State, RH>) => {
    allMiddleware.push(mw);
  };
  const { reducer, createActions } = createReducer(initialState, reducers);

  const reduceSafely = (state: State, action: ReducerActionOf<RH>) => {
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
    action: ReducerActionOf<RH>,
  ) => {
    for (const mw of allMiddleware) {
      try {
        mw(prev, next, action);
      } catch (error) {
        Logger.error(`Error in middleware for action ${action.type}:`, error);
      }
    }
  };

  const reducerWithMiddleware = (state: State, action: ReducerActionOf<RH>) => {
    const next = reduceSafely(state, action);
    runMiddleware(state, next, action);
    return next;
  };

  const valueAtom = atom(initialState());
  // map of SetAtom => Actions, with and without middleware
  const actionsMap = new WeakMap();
  const plainActionsMap = new WeakMap();

  function useActions(
    options: { skipMiddleware?: boolean } = {},
  ): ReducerActions<RH> {
    const setState = useSetAtom(valueAtom);
    const skipMiddleware = options.skipMiddleware === true;
    const cache = skipMiddleware ? plainActionsMap : actionsMap;

    if (!cache.has(setState)) {
      cache.set(
        setState,
        createActions((action: ReducerActionOf<RH>) => {
          // Reduce inside the write. Middleware runs once the write has
          // committed and its subscribers have run, so anything it sets in
          // turn observes the new state rather than the one being replaced.
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
        }),
      );
    }

    // oxlint-disable-next-line typescript/no-non-null-assertion
    return cache.get(setState)!;
  }

  return {
    reducer: reducerWithMiddleware,
    addMiddleware,
    createActions,
    valueAtom,
    useActions,
  };
}
