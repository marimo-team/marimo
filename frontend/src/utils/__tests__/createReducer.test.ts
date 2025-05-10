/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { createReducer, createReducerAndAtoms } from "../createReducer";

interface State {
  count: number;
}

describe("createReducer", () => {
  it("should create a reducer and actions", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
      decrement: (state: State, payload: number) => ({
        count: state.count - payload,
      }),
    };

    const { reducer, createActions } = createReducer(initialState, reducers);

    const dispatch = vi.fn();
    const actions = createActions(dispatch);

    expect(typeof reducer).toBe("function");
    expect(typeof actions.increment).toBe("function");
    expect(typeof actions.decrement).toBe("function");

    actions.increment(5);
    expect(dispatch).toHaveBeenCalledWith({ type: "increment", payload: 5 });

    actions.decrement(3);
    expect(dispatch).toHaveBeenCalledWith({ type: "decrement", payload: 3 });
  });

  it("actions are the same reference", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };

    const { createActions } = createReducer(initialState, reducers);
    const actions = createActions(vi.fn());

    expect(actions.increment).toBe(actions.increment);
  });

  it("can destructure actions", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };

    const { createActions } = createReducer(initialState, reducers);

    const dispatch = vi.fn();
    const { increment } = createActions(dispatch);

    expect(typeof increment).toBe("function");

    increment(5);
    expect(dispatch).toHaveBeenCalledWith({ type: "increment", payload: 5 });
  });

  it("should handle undefined state", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };

    const { reducer } = createReducer(initialState, reducers);

    const newState = reducer(undefined as unknown as State, {
      type: "increment",
      payload: 5,
    });
    expect(newState).toEqual({ count: 5 });
  });

  it("should log error for undefined action type", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {};

    const { reducer } = createReducer(initialState, reducers);
    const loggerSpy = vi.spyOn(Logger, "error");

    const state = { count: 0 };
    const newState = reducer(state, { type: "nonexistent", payload: null });

    expect(newState).toBe(state);
    expect(loggerSpy).toHaveBeenCalledWith(
      "Action type nonexistent is not defined in reducers.",
    );
  });
});

describe("createReducerAndAtoms", () => {
  it("should create reducer, actions, and atoms", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };

    const result = createReducerAndAtoms(initialState, reducers);

    expect(typeof result.reducer).toBe("function");
    expect(typeof result.createActions).toBe("function");
    expect(typeof result.valueAtom).toBe("object");
    expect(typeof result.useActions).toBe("function");
  });

  it("should apply middleware", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };
    const middleware = vi.fn();

    const { reducer } = createReducerAndAtoms(initialState, reducers, [
      middleware,
    ]);

    const state = { count: 0 };
    const action = { type: "increment", payload: 5 };
    reducer(state, action);

    expect(middleware).toHaveBeenCalledWith(state, { count: 5 }, action);
  });

  it("should log an error for non-existent action types", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };
    const loggerSpy = vi.spyOn(Logger, "error");

    const { reducer } = createReducerAndAtoms(initialState, reducers);
    const state = { count: 0 };
    const newState = reducer(state, { type: "nonexistent", payload: null });

    expect(newState).toBe(state);
    expect(loggerSpy).toHaveBeenCalledWith(
      "Action type nonexistent is not defined in reducers.",
    );
  });

  it("should handle errors thrown by actions", () => {
    const initialState = () => ({ count: 0 });
    const errorMessage = "Test error in reducer";
    const reducers = {
      buggyAction: () => {
        throw new Error(errorMessage);
      },
    };
    const originalLoggerError = Logger.error;
    Logger.error = vi.fn();

    const { reducer } = createReducerAndAtoms(initialState, reducers);
    const state = { count: 0 };
    const newState = reducer(state, { type: "buggyAction", payload: null });

    expect(newState).toBe(state);
    expect(Logger.error).toHaveBeenCalledWith(
      "Error in reducer for action buggyAction:",
      expect.any(Error),
    );

    Logger.error = originalLoggerError;
  });
});
