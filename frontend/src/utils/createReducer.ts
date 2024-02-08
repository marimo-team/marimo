/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { Logger } from "@/utils/Logger";
import { NoInfer } from "@tanstack/react-table";
import { Reducer } from "react";

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
