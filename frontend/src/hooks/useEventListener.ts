/* Copyright 2024 Marimo. All rights reserved. */
import { type RefObject, useEffect, useRef } from "react";

/**
 * A type that makes it clear that an `HTMLElement` is not derived from a `RefObject`.
 * If an `HTMLElement` is derived from a `RefObject`, then pass that in directly.
 *
 * This doesn't actually do anything at runtime (it is just a type annotation), but
 * this forces the user to check that the `targetValue` is not a `RefObject`.
 */
export type HTMLElementNotDerivedFromRef<T = HTMLElement> = T & {
  __brand: "HTMLElementNotDerivedFromRef";
};

export function isRefObject<T>(target: unknown): target is RefObject<T | null> {
  return target !== null && typeof target === "object" && "current" in target;
}

export function useEventListener<K extends keyof DocumentEventMap>(
  targetValue: Document,
  type: K,
  listener: (ev: DocumentEventMap[K]) => unknown,
  options?: boolean | AddEventListenerOptions,
): void;
export function useEventListener<K extends keyof WindowEventMap>(
  targetValue: Window,
  type: K,
  listener: (ev: WindowEventMap[K]) => unknown,
  options?: boolean | AddEventListenerOptions,
): void;
export function useEventListener<K extends keyof HTMLElementEventMap>(
  targetValue:
    | HTMLElementNotDerivedFromRef
    | RefObject<HTMLElement | null>
    | null,
  type: K,
  listener: (ev: HTMLElementEventMap[K]) => unknown,
  options?: boolean | AddEventListenerOptions,
): void;
export function useEventListener(
  targetValue: EventTarget | RefObject<EventTarget | null> | null,
  type: string,
  listener: (ev: Event) => unknown,
  options?: boolean | AddEventListenerOptions,
): void {
  const savedListener = useRef(listener);

  useEffect(() => {
    savedListener.current = listener;
  }, [listener]);

  useEffect(() => {
    // Get the actual target, whether it's from a ref or direct value
    // We get ref.current inside the effect instead of during render because changes to ref.current will not trigger a re-render
    const target = isRefObject(targetValue) ? targetValue.current : targetValue;
    if (!target) {
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const eventListener = (event: any) => savedListener.current(event);
    target.addEventListener(type, eventListener, options);

    return () => {
      target.removeEventListener(type, eventListener, options);
    };
  }, [type, targetValue, options]);
}
