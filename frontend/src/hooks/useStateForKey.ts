/* Copyright 2026 Marimo. All rights reserved. */
import { type SetStateAction, useCallback, useReducer } from "react";

interface KeyedState<T> {
  key: unknown;
  value: T;
}

type KeyedAction<T> =
  | { type: "reset"; state: KeyedState<T> }
  | { type: "update"; key: unknown; update: SetStateAction<T> };

function reduceKeyedState<T>(
  previous: KeyedState<T>,
  action: KeyedAction<T>,
): KeyedState<T> {
  if (action.type === "reset") {
    return action.state;
  }
  if (!Object.is(previous.key, action.key)) {
    return previous;
  }
  const value =
    typeof action.update === "function"
      ? (action.update as (previous: T) => T)(previous.value)
      : action.update;
  return Object.is(previous.value, value)
    ? previous
    : { key: action.key, value };
}

/**
 * Local state that resets when its owner key changes.
 *
 * The key uses Object.is. NaN matches NaN, 0 differs from -0, and objects match
 * by reference. Keep the key stable between resets. An inline object such as
 * `{ id }` creates a new key on each render and causes a render loop.
 *
 * On a key change, this hook calls initialize() and schedules a state update
 * during render. React retries the calling component before rendering its
 * children. Children and effects receive the reset value without an intervening
 * commit of the old value. This resets only this hook's state. The component
 * stays mounted, and its other hooks keep their state.
 *
 * initialize must be pure. React can call it more than once in Strict Mode or
 * when retrying an interrupted render. A new initializer alone does not reset
 * state. The next key change uses the initializer from that render. After
 * committed key changes A -> B -> A, A starts fresh instead of restoring its
 * earlier value. If React abandons a pending render for B, the visible state
 * for A remains intact, including edits made while B was pending.
 *
 * The setter accepts values or pure updater functions, like useState. To store
 * a function, use setValue(() => callback). Its identity is stable for the same
 * key and changes with the key. Updates from a different key are ignored,
 * including their updater functions. After A -> B -> A, an old setter for A
 * can update A again. This hook does not cancel requests. For request results,
 * use a distinct key for each lifetime so late results stay invalid.
 *
 * React can still call the component for ignored or same-value updates.
 * Render counts do not indicate how many changes React commits to the screen.
 *
 * Use useInternalStateWithSync when the external value itself supplies the
 * reset value. Use this hook when a separate key controls the reset.
 *
 * @example
 * const [expanded, setExpanded] = useStateForKey(tree, () => new Set<string>());
 *
 * @see https://react.dev/reference/react/useState#storing-information-from-previous-renders
 */
export function useStateForKey<T>(key: unknown, initialize: () => T) {
  // useState can eagerly evaluate an updater against a suspended render's
  // state. A reducer checks the key when React processes each render's queue,
  // so the still-visible owner can accept edits during a transition.
  const [stored, dispatch] = useReducer(reduceKeyedState<T>, key, (key) => ({
    key,
    value: initialize(),
  }));
  const current = Object.is(stored.key, key)
    ? stored
    : { key, value: initialize() };
  if (current !== stored) {
    dispatch({ type: "reset", state: current });
  }

  const setValue = useCallback(
    (update: SetStateAction<T>) => {
      dispatch({ type: "update", key, update });
    },
    [key],
  );

  return [current.value, setValue] as const;
}
