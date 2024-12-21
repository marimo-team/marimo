/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { EditorView } from "@codemirror/view";
import { dndBundle } from "../dnd";
import { describe, beforeEach, afterEach, it, expect } from "vitest";

describe("dnd", () => {
  let view: EditorView;

  beforeEach(() => {
    const el = document.createElement("div");
    view = new EditorView({
      parent: el,
    });
  });

  afterEach(() => {
    view.destroy();
  });

  it("handles text file drops", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dropHandler = handlers.drop;

    const file = new File(["test content"], "test.txt", { type: "text/plain" });
    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
    });
    event.dataTransfer?.items.add(file);

    const result = dropHandler(event, view);
    expect(result).toBe(true);
    expect(event.defaultPrevented).toBe(true);
  });

  it("handles image file drops", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dropHandler = handlers.drop;

    const file = new File([""], "test.png", { type: "image/png" });
    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
    });
    event.dataTransfer?.items.add(file);

    const result = dropHandler(event, view);
    expect(result).toBe(true);
    expect(event.defaultPrevented).toBe(true);
  });

  it("handles plain text drops", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dropHandler = handlers.drop;

    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
      clientX: 0,
      clientY: 0,
    });
    event.dataTransfer?.setData("text/plain", "dropped text");

    const result = dropHandler(event, view);
    expect(result).toBe(true);
    expect(event.defaultPrevented).toBe(true);
  });

  it("prevents default on dragover", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dragoverHandler = handlers.dragover;

    const event = new DragEvent("dragover");
    dragoverHandler(event);
    expect(event.defaultPrevented).toBe(true);
  });
});
