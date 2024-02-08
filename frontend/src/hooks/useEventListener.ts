/* Copyright 2024 Marimo. All rights reserved. */
import { useRef, useEffect } from "react";

type Target = Document | HTMLElement | Window | null;
type EventMap<T extends Target> = T extends Document
  ? DocumentEventMap
  : T extends HTMLElement
    ? HTMLElementEventMap
    : T extends Window
      ? WindowEventMap
      : never;

export function useEventListener<T extends Target, K extends keyof EventMap<T>>(
  target: T,
  type: K & string,
  listener: (ev: EventMap<T>[K]) => unknown,
  options?: boolean | AddEventListenerOptions,
): void {
  const savedListener = useRef(listener);

  useEffect(() => {
    savedListener.current = listener;
  }, [listener]);

  useEffect(() => {
    if (!target) {
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const eventListener = (event: any) => savedListener.current(event);
    target.addEventListener(type, eventListener, options);

    return () => {
      target.removeEventListener(type, eventListener, options);
    };
  }, [type, target, options]);
}
