/* Copyright 2023 Marimo. All rights reserved. */
import { useRef, useEffect } from "react";

export function useEventListener<K extends keyof DocumentEventMap>(
  type: K,
  listener: (ev: DocumentEventMap[K]) => unknown,
  options?: boolean | AddEventListenerOptions
): void {
  const savedListener = useRef(listener);

  useEffect(() => {
    savedListener.current = listener;
  }, [listener]);

  useEffect(() => {
    const eventListener = (event: DocumentEventMap[K]) =>
      savedListener.current(event);
    document.addEventListener(type, eventListener, options);

    return () => {
      document.removeEventListener(type, eventListener, options);
    };
  }, [type, options]);
}

export function useWindowEventListener<K extends keyof WindowEventMap>(
  type: K,
  listener: (ev: WindowEventMap[K]) => unknown,
  options?: boolean | AddEventListenerOptions
): void {
  const savedListener = useRef(listener);

  useEffect(() => {
    savedListener.current = listener;
  }, [listener]);

  useEffect(() => {
    const eventListener = (event: WindowEventMap[K]) =>
      savedListener.current(event);
    window.addEventListener(type, eventListener, options);

    return () => {
      window.removeEventListener(type, eventListener, options);
    };
  }, [type, options]);
}
