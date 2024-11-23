/* Copyright 2024 Marimo. All rights reserved. */
import { useRef, useEffect, type RefObject } from "react";

type Target = Document | HTMLElement | Window | null;
type TargetRef = RefObject<Target>;
type TargetValue = Target | TargetRef;
type EventMap<T extends Target> = T extends Document
  ? DocumentEventMap
  : T extends HTMLElement
    ? HTMLElementEventMap
    : T extends Window
      ? WindowEventMap
      : never;

function isRefObject<T>(target: T | RefObject<T>): target is RefObject<T> {
  return target !== null && typeof target === "object" && "current" in target;
}

export function useEventListener<T extends Target, K extends keyof EventMap<T>>(
  targetValue: TargetValue,
  type: K & string,
  listener: (ev: EventMap<T>[K]) => unknown,
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
