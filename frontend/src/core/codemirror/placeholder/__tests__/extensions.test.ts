/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clickablePlaceholderExtension,
  smartPlaceholderExtension,
} from "../extensions";

describe("smartPlaceholderExtension", () => {
  const placeholderText = "Type something...";
  let view: EditorView;

  beforeEach(() => {
    view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: smartPlaceholderExtension(placeholderText),
      }),
    });
  });

  afterEach(() => {
    view.destroy();
  });

  it("should insert placeholder on ArrowRight when empty", () => {
    // Simulate ArrowRight key
    const event = new KeyboardEvent("keydown", { key: "ArrowRight" });
    view.contentDOM.dispatchEvent(event);

    expect(view.state.doc.toString()).toBe(placeholderText);
    expect(view.state.selection.main.head).toBe(placeholderText.length);
  });

  it("should insert placeholder on Tab when empty", () => {
    // Simulate Tab key
    const event = new KeyboardEvent("keydown", { key: "Tab" });
    view.contentDOM.dispatchEvent(event);

    expect(view.state.doc.toString()).toBe(placeholderText);
    expect(view.state.selection.main.head).toBe(placeholderText.length);
  });

  it("should not insert placeholder when not empty", () => {
    // Add some content
    view.dispatch({
      changes: { from: 0, insert: "existing content" },
    });

    // Simulate ArrowRight key
    const event = new KeyboardEvent("keydown", { key: "ArrowRight" });
    view.contentDOM.dispatchEvent(event);

    expect(view.state.doc.toString()).toBe("existing content");
  });
});

describe("clickablePlaceholderExtension", () => {
  it("should create placeholder with clickable link", () => {
    const onClick = vi.fn();
    const opts = {
      beforeText: "Click ",
      linkText: "here",
      afterText: " to continue",
      onClick,
    };

    const extension = clickablePlaceholderExtension(opts);
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: extension,
      }),
    });

    // Get the placeholder element
    const placeholder = view.dom.querySelector(".cm-placeholder")!;
    expect(placeholder).toBeTruthy();

    // Check text content
    expect(placeholder.textContent).toBe("Click here to continue");

    // Find and check the clickable link
    const link = placeholder.querySelector(".cm-clickable-placeholder")!;
    expect(link).toBeTruthy();
    expect(link.textContent).toBe("here");

    // Simulate click
    (link as HTMLElement).click();
    expect(onClick).toHaveBeenCalled();

    // Check theme classes
    expect(link.classList.contains("cm-clickable-placeholder")).toBe(true);

    view.destroy();
  });

  it("should stop event propagation on link click", () => {
    const onClick = vi.fn();
    const opts = {
      beforeText: "Click ",
      linkText: "here",
      afterText: " to continue",
      onClick,
    };

    const extension = clickablePlaceholderExtension(opts);
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: extension,
      }),
    });

    // Get the link element
    const link = view.dom.querySelector(".cm-clickable-placeholder")!;

    // Create a mock event
    const event = new MouseEvent("click");
    const stopPropagation = vi.spyOn(event, "stopPropagation");

    // Simulate click with the mock event
    link.dispatchEvent(event);

    expect(stopPropagation).toHaveBeenCalled();
    expect(onClick).toHaveBeenCalled();

    view.destroy();
  });
});
