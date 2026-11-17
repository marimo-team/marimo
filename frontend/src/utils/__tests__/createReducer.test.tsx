/* Copyright 2026 Marimo. All rights reserved. */
import { act, renderHook } from "@testing-library/react";
import { createStore, getDefaultStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { describe, expect, expectTypeOf, it, vi } from "vitest";
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

  it("preserves action names and payload types through reducers and atoms", () => {
    const initialState = () => ({ count: 0 });
    const { reducer, createActions, useActions } = createReducerAndAtoms(
      initialState,
      {
        increment: (state, payload: number) => ({
          count: state.count + payload,
        }),
        setFromText: (_state, payload: string) => ({ count: payload.length }),
        reset: () => initialState(),
      },
      [
        (_prevState, _newState, action) => {
          if (action.type === "increment") {
            expectTypeOf(action.payload).toEqualTypeOf<number>();
          }
          if (action.type === "setFromText") {
            expectTypeOf(action.payload).toEqualTypeOf<string>();
          }
        },
      ],
    );
    const dispatch = vi.fn();
    const actions = createActions(dispatch);

    expectTypeOf(actions).toEqualTypeOf<{
      increment: (payload: number) => void;
      setFromText: (payload: string) => void;
      reset: () => void;
    }>();
    expectTypeOf<ReturnType<typeof useActions>>().toEqualTypeOf<
      typeof actions
    >();
    expectTypeOf(reducer)
      .parameter(1)
      .toEqualTypeOf<
        | { type: "increment"; payload: number }
        | { type: "setFromText"; payload: string }
        | { type: "reset"; payload: unknown }
      >();

    // @ts-expect-error - action names determine their payload types
    expectTypeOf(reducer).toBeCallableWith(initialState(), {
      type: "increment",
      payload: "5",
    });
    // @ts-expect-error - action creators reject incorrect payloads
    expectTypeOf(actions.setFromText).toBeCallableWith(5);

    actions.increment(5);
    actions.setFromText("hello");
    actions.reset();
    expect(dispatch.mock.calls).toEqual([
      [{ type: "increment", payload: 5 }],
      [{ type: "setFromText", payload: "hello" }],
      [{ type: "reset", payload: undefined }],
    ]);
    expect(
      reducer(initialState(), { type: "setFromText", payload: "hello" }),
    ).toEqual({ count: 5 });
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
    // @ts-expect-error - exercise runtime handling of an invalid action
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

  it("caches hook actions and supports bypassing middleware", () => {
    const middleware = vi.fn();
    const { useActions, valueAtom } = createReducerAndAtoms(
      () => ({ count: 0 }),
      {
        increment: (state, payload: number) => ({
          count: state.count + payload,
        }),
      },
      [middleware],
    );
    const { result, rerender } = renderHook((options) => useActions(options), {
      initialProps: { skipMiddleware: false },
    });
    const actions = result.current;
    act(() => actions.increment(2));
    rerender({ skipMiddleware: false });
    expect(result.current).toBe(actions);
    expect(getDefaultStore().get(valueAtom)).toEqual({ count: 2 });
    expect(middleware).toHaveBeenCalledExactlyOnceWith(
      { count: 0 },
      { count: 2 },
      { type: "increment", payload: 2 },
    );

    middleware.mockClear();
    rerender({ skipMiddleware: true });
    const plainActions = result.current;
    rerender({ skipMiddleware: true });
    expect(result.current).toBe(plainActions);
    act(() => result.current.increment(3));
    expect(getDefaultStore().get(valueAtom)).toEqual({ count: 5 });
    expect(middleware).not.toHaveBeenCalled();
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
    const action = { type: "increment", payload: 5 } as const;
    reducer(state, action);

    expect(middleware).toHaveBeenCalledWith(state, { count: 5 }, action);
  });

  it("runs middleware after the write commits, so it sees the new state", () => {
    const initialState = () => ({ count: 0 });
    const reducers = {
      increment: (state: State, payload: number) => ({
        count: state.count + payload,
      }),
    };
    const seen: number[] = [];
    const { valueAtom, useActions } = createReducerAndAtoms(
      initialState,
      reducers,
      [(_prev, next) => seen.push(store.get(valueAtom).count, next.count)],
    );
    const store = createStore();
    const wrapper = ({ children }: PropsWithChildren) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(() => useActions(), { wrapper });

    result.current.increment(5);

    expect(seen).toEqual([5, 5]);
    expect(store.get(valueAtom)).toEqual({ count: 5 });
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
    // @ts-expect-error - we are testing this
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
