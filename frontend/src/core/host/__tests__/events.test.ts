/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { z } from "zod";
import { parseNotebookEvent } from "../events";

describe("notebook messages", () => {
  it("normalizes session and host envelopes for native marimo messages", () => {
    const notification = {
      op: "variables",
      variables: [{ name: "x", value: Number.NaN }],
    };
    const host = { event: "marimo", data: { marimo: notification } };
    expect(parseNotebookEvent({ data: notification })).toEqual(host);
    expect(parseNotebookEvent({ ...host, id: "42" })).toEqual({
      ...host,
      id: "42",
    });
  });

  it("retains unknown event cursors without interpreting their payloads", () => {
    expect(
      parseNotebookEvent({ event: "future", id: "42", data: null }),
    ).toEqual({ event: "unknown", name: "future", id: "42" });
  });

  it.each([
    { event: "cell", id: "42", data: { cell: { id: "c1" } } },
    { event: "ready", data: {} },
    { event: "marimo", data: { marimo: {} } },
    { data: {} },
    null,
  ])("rejects malformed known messages: %j", (message) => {
    expect(() => parseNotebookEvent(message)).toThrow(z.ZodError);
  });
});
