/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import { NoInfer } from "@tanstack/react-table";
import { atom, useSetAtom } from "jotai";
import { Reducer, useMemo } from "react";

interface ReducerAction<T> {
  type: string;
  payload: T;
}

type Dispatch = (action: ReducerAction<any>) => void;
type IfUnknown<T, Y, N> = unknown extends T ? Y : N;

type ReducerHandler<State, Payload> = (state: State, payload: Payload) => State;

interface ReducerHandlers<State> {
  [K: string]: ReducerHandler<State, any>;
}

type ReducerActions<RH extends ReducerHandlers<any>> = {
  [Type in keyof RH]: RH[Type] extends ReducerHandler<any, infer Payload>
    ? IfUnknown<Payload, () => void, (payload: Payload) => void>
    : never;
};

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
  createActions: (dispatch: Dispatch) => ReducerActions<RH>;
}

/**
 * Utility function to create a reducer and its actions.
 */
export function createReducer<
  State,
  RH extends ReducerHandlers<NoInfer<State>>,
>(initialState: () => State, reducers: RH): ReducerCreatorResult<State, RH> {
  return {
    reducer: (state, action: ReducerAction<RH>) => {
      state = state || initialState();
      if (action.type in reducers) {
        return reducers[action.type](state, action.payload);
      } else {
        Logger.error(`Action type ${action.type} is not defined in reducers.`);
      }
      return state;
    },
    createActions: (dispatch: Dispatch) => {
      const actions = {} as ReducerActions<RH>;
      for (const type in reducers) {
        (actions as any)[type] = (payload: any) => {
          dispatch({ type, payload });
        };
      }
      return actions;
    },
  };
}

type Middleware<State> = (
  prevState: State,
  newState: State,
  action: ReducerAction<any>,
) => void;

export function createReducerAndAtoms<
  State,
  RH extends ReducerHandlers<NoInfer<State>>,
>(
  initialState: () => State,
  reducers: RH,
  middleware?: Array<Middleware<State>>,
) {
  const { reducer, createActions } = createReducer(initialState, reducers);

  const reducerWithMiddleware = (state: State, action: ReducerAction<any>) => {
    const newState = reducer(state, action);
    if (middleware) {
      for (const mw of middleware) {
        mw(state, newState, action);
      }
    }
    return newState;
  };

  const valueAtom = atom(initialState());

  function useActions() {
    const setState = useSetAtom(valueAtom);

    return useMemo(() => {
      const actions = createActions((action) => {
        setState((state) => reducerWithMiddleware(state, action));
      });
      return actions;
    }, [setState]);
  }

  return {
    reducer: reducerWithMiddleware,
    createActions,
    valueAtom,
    useActions,
  };
}
