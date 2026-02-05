/* Copyright 2026 Marimo. All rights reserved. */
import { debounce } from "lodash-es";
import { useEffect, useMemo, useState } from "react";
import useEvent from "react-use-event-hook";

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * A hook that allows you to control a state value, but also get a debounced version of that value.
 */
export function useDebounceControlledState<T>(opts: {
  /**
   * Initial value of the state.
   */
  initialValue: T;
  /**
   * Callback to run when the state changes.
   * This will be debounced.
   */
  onChange: (value: T) => void;
  /**
   * The delay to debounce the state change by.
   * @default 200
   */
  delay?: number;
  /**
   * Whether the state is disabled.
   */
  disabled?: boolean;
}) {
  const { initialValue, onChange, delay, disabled } = opts;
  const [internalValue, setInternalValue] = useState<T>(initialValue);
  const debouncedValue = useDebounce(internalValue, delay || 200);

  const onUpdate = useEvent(onChange);

  // Handle external changes:
  useEffect(() => {
    setInternalValue(initialValue);
  }, [initialValue]);

  // Handle debounced updates for user input
  useEffect(() => {
    if (disabled) {
      return;
    }
    // Only trigger debounced update if the value is different from initialValue
    if (debouncedValue !== initialValue) {
      onUpdate(debouncedValue);
    }
  }, [debouncedValue, disabled, onUpdate]);

  // If disabled, just pass through the initialValue and onChange
  if (disabled) {
    return {
      value: internalValue,
      debouncedValue: internalValue,
      onChange: onChange,
    };
  }

  return {
    value: internalValue,
    debouncedValue,
    onChange: setInternalValue,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useDebouncedCallback<T extends (...args: any[]) => unknown>(
  callback: T,
  delay: number,
) {
  const internalCallback = useEvent(callback);
  return useMemo(() => {
    return debounce(internalCallback, delay);
  }, [internalCallback, delay]);
}
