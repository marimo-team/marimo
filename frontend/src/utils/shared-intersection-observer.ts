/* Copyright 2026 Marimo. All rights reserved. */
import { createSharedResource } from "./shared-resource";

/** One observer per options set, with independently disposable subscriptions. */
export function createSharedIntersectionObserver(
  options: IntersectionObserverInit,
) {
  const subscribers = new Map<Element, Set<(visible: boolean) => void>>();
  let observer: IntersectionObserver | undefined;
  const acquire = createSharedResource(() => {
    const current = new IntersectionObserver((entries) => {
      if (observer !== current) {
        return;
      }
      for (const entry of entries) {
        const callbacks = subscribers.get(entry.target);
        const snapshot = [...(callbacks ?? [])];
        for (const callback of snapshot) {
          if (callbacks?.has(callback)) {
            callback(entry.isIntersecting);
          }
        }
      }
    }, options);
    observer = current;
    return () => {
      observer = undefined;
      current.disconnect();
    };
  });

  return (target: Element, onChange: (visible: boolean) => void) => {
    const release = acquire();
    const callback = (visible: boolean) => onChange(visible);
    let callbacks = subscribers.get(target);
    if (!callbacks) {
      callbacks = new Set();
      subscribers.set(target, callbacks);
      observer?.observe(target);
    }
    callbacks.add(callback);
    return () => {
      if (!callbacks.delete(callback)) {
        return;
      }
      if (callbacks.size === 0) {
        subscribers.delete(target);
        observer?.unobserve(target);
      }
      release();
    };
  };
}
