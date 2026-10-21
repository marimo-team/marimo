/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { attachments } from "../resources/attachments";
import { createReducer } from "@marimo-team/client/reducer";
import { fixtureEvents } from "./fixtures";

const reducer = createReducer({ attachments });
const snapshot = fixtureEvents("notebook-events.sse");
const records = snapshot.flatMap((event) =>
  event.event === "attachment" ? [event.data.attachment] : [],
);
const confirmed = () => snapshot.reduce(reducer.reduce, reducer.initial);

describe("attachment resource", () => {
  it("collects snapshot records, replaces by id, and removes attachments", () => {
    const state = confirmed();
    expect(state.resources.attachments).toEqual(records);
    const [browser, agent] = records;
    const renamed = { ...agent, name: "Renamed agent" };
    const updated = reducer.reduce(state, {
      event: "attachment",
      id: "98",
      data: { attachment: renamed },
    });
    expect(updated.resources.attachments).toEqual([browser, renamed]);
    expect(state.resources.attachments).toEqual(records);

    const removed = reducer.reduce(updated, {
      event: "attachment.removed",
      id: "99",
      data: { id: browser.id, time: "2026-10-01T09:30:00Z" },
    });
    expect(removed.resources.attachments).toEqual([renamed]);
    const repeated = reducer.reduce(removed, {
      event: "attachment.removed",
      id: "100",
      data: { id: browser.id, time: "2026-10-01T09:30:00Z" },
    });
    expect(repeated.resources.attachments).toBe(removed.resources.attachments);
  });

  it("rebuilds records after reset", () => {
    const state = confirmed();
    const reset = reducer.reduce(state, { event: "reset", data: {} });
    expect(reset.resources.attachments).toEqual([]);
    const replacement = snapshot
      .filter(
        (event) =>
          event.event !== "attachment" ||
          event.data.attachment.id === records[0].id,
      )
      .reduce(reducer.reduce, reset);
    expect(replacement.resources.attachments).toEqual([records[0]]);
  });
});
