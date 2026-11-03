/* Copyright 2026 Marimo. All rights reserved. */

import { expect, it } from "vitest";
import { EventStream } from "../transport/stream.ts";

it("delivers partial updates with the UI element kind", () => {
  const stream = new EventStream({ types: ["ui_element"] }, ["ui_element"]);
  const events: unknown[] = [];
  stream.subscribe((event) => events.push(event));
  const update = {
    event: "ui_element.update",
    id: "2",
    data: {
      id: "Hbol-0",
      state: { value: 4 },
      request_id: "r1",
      time: "2026-11-03T22:00:00Z",
    },
  };
  stream.receive({ event: "ready", data: {}, id: "1" });
  stream.receive(update);
  expect(events).toEqual([{ event: "ready", data: {}, id: "1" }, update]);
  expect(stream.cursor).toBe("2");
});

it("keeps the cursor when UI elements are excluded", () => {
  const stream = new EventStream({ types: ["cell"] }, ["cell", "ui_element"]);
  const events: unknown[] = [];
  stream.subscribe((event) => events.push(event));
  stream.receive({
    event: "ui_element.update",
    data: { id: "Hbol-0", state: { value: 4 }, time: "2026-11-03T22:00:00Z" },
    id: "2",
  });
  expect(events).toEqual([]);
  expect(stream.cursor).toBe("2");
});
