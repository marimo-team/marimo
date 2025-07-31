/* Copyright 2024 Marimo. All rights reserved. */

// Track current key sequence per element
const sequenceTracker = new WeakMap<
  EventTarget,
  {
    sequence: string;
    timeout: number;
  }
>();

const SEQUENCE_TIMEOUT = 500;

function getKeyString(evt: KeyboardEvent): string {
  // Skip if modifiers are pressed (except shift)
  if (evt.ctrlKey || evt.metaKey || evt.altKey) {
    return "";
  }
  const key = evt.key.toLowerCase();
  return evt.shiftKey ? `shift+${key}` : key;
}

export function handleVimKeybinding(
  evt: KeyboardEvent,
  bindings: Record<string, () => boolean>,
): boolean {
  const key = getKeyString(evt);
  const target = evt.target;
  if (!key || !target) {
    return false;
  }

  const tracker = sequenceTracker.get(target);
  let sequence = key;

  // clear any existing timeout
  if (tracker?.timeout) {
    clearTimeout(tracker.timeout);
  }

  // continue building sequence if we have a previous key
  if (tracker) {
    sequence = `${tracker.sequence} ${key}`;
  }

  // check exact match
  const action = bindings[sequence];
  if (action) {
    sequenceTracker.delete(target);
    return action();
  }

  // IMPORTANT: We eagerly match single keys even if they could be part of a sequence
  // For example, if bindings has both "g" and "g g", pressing "g" will immediately trigger "g"
  // This means "g g" would never be triggered in that case
  if (!tracker) {
    const singleKeyAction = bindings[key];
    if (singleKeyAction) {
      return singleKeyAction();
    }
  }

  const couldContinue = Object.keys(bindings).some((binding) =>
    binding.startsWith(`${sequence} `),
  );

  if (couldContinue) {
    // store partial sequence
    const timeout = window.setTimeout(() => {
      sequenceTracker.delete(target);
    }, SEQUENCE_TIMEOUT);
    sequenceTracker.set(target, { sequence, timeout });
    return true; // prevent default while waiting
  }

  // No match
  sequenceTracker.delete(target);
  return false;
}

export const testHelpers = {
  clearSequenceTracker: (target: EventTarget) => {
    const tracker = sequenceTracker.get(target);
    if (tracker?.timeout) {
      clearTimeout(tracker.timeout);
    }
    sequenceTracker.delete(target);
  },
  SEQUENCE_TIMEOUT,
};
