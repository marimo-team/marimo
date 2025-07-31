/* Copyright 2024 Marimo. All rights reserved. */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type Mock,
  vi,
} from "vitest";
import { handleVimKeybinding, testHelpers } from "./vim-bindings";

function createKeyEvent(
  target: EventTarget,
  { key, shiftKey = false }: { key: string; shiftKey?: boolean },
): KeyboardEvent {
  const event = new KeyboardEvent("keydown", {
    key,
    shiftKey,
  });
  // Manually set target since KeyboardEvent constructor doesn't support it
  Object.defineProperty(event, "target", {
    value: target,
    writable: false,
  });
  return event;
}

describe("handleVimKeybinding", () => {
  let target: EventTarget;
  let mockActions: Record<string, Mock>;
  let bindings: Record<string, () => boolean>;

  beforeEach(() => {
    vi.useFakeTimers();
    target = new EventTarget();
    mockActions = {
      moveDown: vi.fn(() => true),
      goToTop: vi.fn(() => true),
    };
    bindings = {
      j: mockActions.moveDown,
      "g g": mockActions.goToTop,
    };
  });

  afterEach(() => {
    testHelpers.clearSequenceTracker(target);
    vi.useRealTimers();
  });

  it("handles single key bindings", () => {
    const result = handleVimKeybinding(
      createKeyEvent(target, { key: "j" }),
      bindings,
    );
    expect(result).toBe(true);
    expect(mockActions.moveDown).toHaveBeenCalledOnce();
  });

  it("handles key sequences", () => {
    // First 'g' - should not trigger anything, but return true to prevent default
    const result1 = handleVimKeybinding(
      createKeyEvent(target, { key: "g" }),
      bindings,
    );
    expect(result1).toBe(true);
    expect(mockActions.goToTop).not.toHaveBeenCalled();

    // Second 'g' - should trigger the action
    const result2 = handleVimKeybinding(
      createKeyEvent(target, { key: "g" }),
      bindings,
    );
    expect(result2).toBe(true);
    expect(mockActions.goToTop).toHaveBeenCalledOnce();
  });

  it("times out incomplete sequences", () => {
    handleVimKeybinding(createKeyEvent(target, { key: "g" }), bindings);
    vi.advanceTimersByTime(testHelpers.SEQUENCE_TIMEOUT + 1);

    // Press 'g' again - should start a new sequence, not complete "g g"
    handleVimKeybinding(createKeyEvent(target, { key: "g" }), bindings);
    expect(mockActions.goToTop).not.toHaveBeenCalled();
  });

  it("eagerly matches single keys even if they could be part of a sequence", () => {
    const eagerBindings = {
      g: vi.fn(() => true),
      "g g": mockActions.goToTop,
    };

    // Press 'g' - should immediately trigger single 'g' action
    const result = handleVimKeybinding(
      createKeyEvent(target, { key: "g" }),
      eagerBindings,
    );
    expect(result).toBe(true);
    expect(eagerBindings.g).toHaveBeenCalledOnce();
    expect(mockActions.goToTop).not.toHaveBeenCalled();

    // Press 'g' again - should trigger single 'g' again, NOT "g g"
    handleVimKeybinding(createKeyEvent(target, { key: "g" }), eagerBindings);
    expect(eagerBindings.g).toHaveBeenCalledTimes(2);
    expect(mockActions.goToTop).not.toHaveBeenCalled();
  });
});
