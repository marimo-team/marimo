/* Copyright 2026 Marimo. All rights reserved. */

/** Start on first acquire, stop on last release. Each release is idempotent. */
export function createSharedResource(start: () => () => void) {
  let users = 0;
  let stop: (() => void) | undefined;
  return () => {
    if (users === 0) {
      stop = start();
    }
    users++;
    let released = false;
    return () => {
      if (released) {
        return;
      }
      released = true;
      if (--users === 0) {
        const cleanup = stop;
        stop = undefined;
        cleanup?.();
      }
    };
  };
}

/** Share an upstream subscription, including React StrictMode mount cycles. */
export function createSharedSubscription(
  start: (notify: () => void) => () => void,
) {
  const subscribers = new Set<() => void>();
  const acquire = createSharedResource(() =>
    start(() => {
      // Subscriptions created during notification wait for the next event.
      const snapshot = [...subscribers];
      for (const subscriber of snapshot) {
        if (subscribers.has(subscriber)) {
          subscriber();
        }
      }
    }),
  );
  return (onChange: () => void) => {
    // Separate registrations of the same callback must have independent lifetimes.
    const notify = () => onChange();
    subscribers.add(notify);
    let release: () => void;
    try {
      release = acquire();
    } catch (error) {
      subscribers.delete(notify);
      throw error;
    }
    return () => {
      subscribers.delete(notify);
      release();
    };
  };
}
