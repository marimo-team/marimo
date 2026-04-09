/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, test } from "vitest";
import { Events } from "../events";

/**
 * Create a minimal fake event with just a target (no composedPath).
 * Simulates synthetic events from libraries like React Aria.
 */
function fakeEvent(target: EventTarget): Pick<Event, "target"> {
  return { target };
}

/**
 * Create a fake native-like KeyboardEvent with composedPath() returning
 * a different element than target — the key scenario for shadow DOM
 * retargeting where target is the shadow host but composedPath()[0]
 * is the real focused element inside the shadow root.
 */
function fakeNativeEvent(
  retargetedHost: EventTarget,
  realTarget: EventTarget,
): KeyboardEvent {
  const event = new KeyboardEvent("keydown");
  Object.defineProperty(event, "target", { value: retargetedHost });
  Object.defineProperty(event, "composedPath", {
    value: () => [realTarget, retargetedHost, document.body, document],
  });
  return event;
}

describe("Events.composedTarget", () => {
  test("returns composedPath()[0] for native events", () => {
    const input = document.createElement("input");
    const host = document.createElement("div");
    const event = fakeNativeEvent(host, input);

    expect(Events.composedTarget(event)).toBe(input);
  });

  test("falls back to e.target when composedPath is absent", () => {
    const div = document.createElement("div");
    const event = fakeEvent(div);

    expect(Events.composedTarget(event)).toBe(div);
  });

  test("falls back to e.target when composedPath returns empty array", () => {
    const div = document.createElement("div");
    const event = new KeyboardEvent("keydown");
    Object.defineProperty(event, "target", { value: div });
    Object.defineProperty(event, "composedPath", { value: () => [] });

    expect(Events.composedTarget(event)).toBe(div);
  });
});

describe("Events.shouldIgnoreKeyboardEvent", () => {
  test("ignores events from <input>", () => {
    const input = document.createElement("input");
    const event = fakeNativeEvent(input, input);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
  });

  test("ignores events from <textarea>", () => {
    const textarea = document.createElement("textarea");
    const event = fakeNativeEvent(textarea, textarea);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
  });

  test("ignores events from <select>", () => {
    const select = document.createElement("select");
    const event = fakeNativeEvent(select, select);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
  });

  test("ignores events from <button>", () => {
    const button = document.createElement("button");
    const event = fakeNativeEvent(button, button);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
  });

  test("ignores events from contentEditable elements", () => {
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    document.body.append(div);

    const event = fakeNativeEvent(div, div);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);

    div.remove();
  });

  test("ignores events from elements with role='textbox'", () => {
    const container = document.createElement("div");
    container.setAttribute("role", "textbox");
    const child = document.createElement("span");
    container.append(child);
    document.body.append(container);

    const event = fakeNativeEvent(child, child);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);

    container.remove();
  });

  test("ignores events from inside .cm-editor", () => {
    const editor = document.createElement("div");
    editor.className = "cm-editor";
    const line = document.createElement("div");
    editor.append(line);
    document.body.append(editor);

    const event = fakeNativeEvent(line, line);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);

    editor.remove();
  });

  test("does NOT ignore events from a plain <div>", () => {
    const div = document.createElement("div");
    const event = fakeNativeEvent(div, div);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(false);
  });

  describe("shadow DOM retargeting (#4230)", () => {
    test("ignores keydown when real target inside shadow root is <input>", () => {
      const host = document.createElement("marimo-text");
      const input = document.createElement("input");
      // event.target is the shadow host, composedPath()[0] is the real input
      const event = fakeNativeEvent(host, input);
      expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
    });

    test("ignores keydown when real target inside shadow root is <textarea>", () => {
      const host = document.createElement("marimo-text-area");
      const textarea = document.createElement("textarea");
      const event = fakeNativeEvent(host, textarea);
      expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
    });

    test("ignores keydown when real target inside shadow root is <select>", () => {
      const host = document.createElement("marimo-dropdown");
      const select = document.createElement("select");
      const event = fakeNativeEvent(host, select);
      expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(true);
    });

    test("does NOT ignore when shadow DOM real target is a plain <div>", () => {
      const host = document.createElement("marimo-output");
      const div = document.createElement("div");
      const event = fakeNativeEvent(host, div);
      expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(false);
    });
  });

  test("does NOT ignore events from non-marimo custom elements", () => {
    const el = document.createElement("sl-input");
    const event = fakeNativeEvent(el, el);
    expect(Events.shouldIgnoreKeyboardEvent(event)).toBe(false);
  });
});

describe("Events.fromInput", () => {
  test("returns true for <input>", () => {
    const input = document.createElement("input");
    expect(Events.fromInput(fakeEvent(input))).toBe(true);
  });

  test("returns true for <textarea>", () => {
    const textarea = document.createElement("textarea");
    expect(Events.fromInput(fakeEvent(textarea))).toBe(true);
  });

  test("returns true for marimo custom elements", () => {
    const el = document.createElement("marimo-slider");
    expect(Events.fromInput(fakeEvent(el))).toBe(true);
  });

  // jsdom does not implement isContentEditable, so this is tested
  // via shouldIgnoreKeyboardEvent which has a closest() fallback.
  test.skip("returns true for contentEditable", () => {
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    document.body.append(div);

    expect(Events.fromInput(fakeEvent(div))).toBe(true);

    div.remove();
  });

  test("returns false for plain <div>", () => {
    const div = document.createElement("div");
    expect(Events.fromInput(fakeEvent(div))).toBe(false);
  });

  test("uses composedPath when available (shadow DOM)", () => {
    const host = document.createElement("div");
    const input = document.createElement("input");
    const event = fakeNativeEvent(host, input);
    expect(Events.fromInput(event)).toBe(true);
  });
});

describe("Events.fromCodeMirror", () => {
  test("returns true when target is inside .cm-editor", () => {
    const editor = document.createElement("div");
    editor.className = "cm-editor";
    const line = document.createElement("div");
    editor.append(line);
    document.body.append(editor);

    expect(Events.fromCodeMirror(line)).toBe(true);
    editor.remove();
  });

  test("returns false when target is not inside .cm-editor", () => {
    const div = document.createElement("div");
    document.body.append(div);
    expect(Events.fromCodeMirror(div)).toBe(false);
    div.remove();
  });
});
