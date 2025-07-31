/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { dndBundle } from "../dnd";

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
    const dropHandler = handlers.domEventHandlers.drop;

    const file = new File(["test content"], "test.txt", { type: "text/plain" });
    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
    });
    event.dataTransfer?.items.add(file);

    const result = dropHandler(event, view);
    expect(result).toBe(true);
  });

  it("handles image file drops", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dropHandler = handlers.domEventHandlers.drop;

    const file = new File([""], "test.png", { type: "image/png" });
    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
    });
    event.dataTransfer?.items.add(file);

    const result = dropHandler(event, view);
    expect(result).toBe(true);
  });

  it("handles plain text drops", () => {
    const extension = dndBundle();
    const handlers = extension[0] as any;
    const dropHandler = handlers.domEventHandlers.drop;

    const event = new DragEvent("drop", {
      dataTransfer: new DataTransfer(),
      clientX: 0,
      clientY: 0,
    });
    event.dataTransfer?.setData("text/plain", "dropped text");

    const result = dropHandler(event, view);
    expect(result).toBe(true);
  });
});

class DragEvent extends Event {
  dataTransfer: DataTransfer;
  clientX: number;
  clientY: number;

  constructor(
    type: string,
    {
      dataTransfer,
      clientX,
      clientY,
    }: { dataTransfer?: DataTransfer; clientX?: number; clientY?: number } = {},
  ) {
    super(type);
    this.dataTransfer = dataTransfer || new DataTransfer();
    this.clientX = clientX || 0;
    this.clientY = clientY || 0;
  }
}

class DataTransfer {
  data: Record<string, string> = {};
  _items: File[] = [];

  setData(type: string, data: string) {
    this.data[type] = data;
  }

  get items() {
    return {
      add: (file: File) => {
        this._items.push(file);
      },
    };
  }

  get files() {
    return this._items;
  }

  getData(type: string) {
    return this.data[type];
  }
}
