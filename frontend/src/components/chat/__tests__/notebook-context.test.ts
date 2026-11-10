/* Copyright 2026 Marimo. All rights reserved. */

import { type UIMessage, validateUIMessages } from "ai";
import { describe, expect, it } from "vitest";
import { withNotebookContext } from "../notebook-context";

const question: UIMessage["parts"] = [{ type: "text", text: "Help me" }];

function user(parts: UIMessage["parts"]): UIMessage {
  return { id: "user", role: "user", parts };
}

function context(data: unknown) {
  return { type: "data-marimo-notebook", data };
}

const initial = {
  sessionId: "session-1",
  cells: { a: "x = 1", b: "y = x + 1" },
};

function initialHistory() {
  return [user(withNotebookContext(question, [], initial))];
}

describe("notebook context", () => {
  it("captures a complete initial snapshot including empty cells", () => {
    expect(
      withNotebookContext(question, [], {
        sessionId: "session-1",
        cells: { a: "" },
      }),
    ).toEqual([
      context({
        sessionId: "session-1",
        cellIds: ["a"],
        cells: [{ id: "a", code: "" }],
      }),
      ...question,
    ]);
  });

  it("sends only a snapshot marker after restoring unchanged history", async () => {
    const restored = await validateUIMessages({
      messages: JSON.parse(JSON.stringify(initialHistory())),
    });
    expect(withNotebookContext(question, restored, initial)).toEqual([
      context({ sessionId: "session-1", cells: [] }),
      ...question,
    ]);
  });

  it("sends only changed or added cells without mutating the history", () => {
    const history = initialHistory();
    const saved = structuredClone(history);
    expect(
      withNotebookContext(question, history, {
        sessionId: "session-1",
        cells: { a: "x = 2", b: "y = x + 1", c: "" },
      }),
    ).toEqual([
      context({
        sessionId: "session-1",
        cellIds: ["a", "b", "c"],
        cells: [
          { id: "a", code: "x = 2" },
          { id: "c", code: "" },
        ],
      }),
      ...question,
    ]);
    expect(history).toEqual(saved);
  });

  it("tracks deletions, reordering, and re-added cells", () => {
    const history = initialHistory();
    const deleted = withNotebookContext(question, history, {
      sessionId: "session-1",
      cells: { b: "y = x + 1" },
    });
    expect(deleted).toEqual([
      context({ sessionId: "session-1", cellIds: ["b"], cells: [] }),
      ...question,
    ]);
    history.push(user(deleted));
    const readded = withNotebookContext(question, history, initial);
    expect(readded).toEqual([
      context({
        sessionId: "session-1",
        cellIds: ["a", "b"],
        cells: [{ id: "a", code: "x = 1" }],
      }),
      ...question,
    ]);
    history.push(user(readded));
    expect(
      withNotebookContext(question, history, {
        sessionId: "session-1",
        cells: { b: "y = x + 1", a: "x = 1" },
      }),
    ).toEqual([
      context({ sessionId: "session-1", cellIds: ["b", "a"], cells: [] }),
      ...question,
    ]);
  });

  it("represents an empty notebook explicitly", () => {
    expect(
      withNotebookContext(question, initialHistory(), {
        sessionId: "session-1",
        cells: {},
      }),
    ).toEqual([
      context({ sessionId: "session-1", cellIds: [], cells: [] }),
      ...question,
    ]);
  });

  it("uses only the retained history when editing a message", () => {
    const history = initialHistory();
    const changed = { sessionId: "session-1", cells: { a: "x = 2" } };
    const next = withNotebookContext(question, history, changed);
    expect(
      withNotebookContext(question, [...history, user(next)], initial),
    ).toEqual([
      context({
        sessionId: "session-1",
        cellIds: ["a", "b"],
        cells: [
          { id: "a", code: "x = 1" },
          { id: "b", code: "y = x + 1" },
        ],
      }),
      ...question,
    ]);
    expect(withNotebookContext(question, history, initial)).toEqual([
      context({ sessionId: "session-1", cells: [] }),
      ...question,
    ]);
  });

  it("updates session identity without repeating code", () => {
    expect(
      withNotebookContext(question, initialHistory(), {
        ...initial,
        sessionId: "session-2",
      }),
    ).toEqual([context({ sessionId: "session-2", cells: [] }), ...question]);
  });

  it("captures a full snapshot for chats created before notebook context existed", () => {
    const legacyHistory = [user(question)];
    expect(withNotebookContext(question, legacyHistory, initial)).toEqual(
      initialHistory()[0].parts,
    );
  });

  it("compares against user snapshots independently of tool results", () => {
    const history = initialHistory();
    history.push({
      id: "tool-result",
      role: "assistant",
      parts: [
        {
          type: "tool-edit_cell",
          toolCallId: "edit-a",
          state: "output-available",
          input: { id: "a", code: "x = 2" },
          output: { code: "x = 2" },
        },
      ],
    });
    expect(
      withNotebookContext(question, history, {
        sessionId: "session-1",
        cells: { a: "x = 2", b: "y = x + 1" },
      }),
    ).toEqual([
      context({
        sessionId: "session-1",
        cells: [{ id: "a", code: "x = 2" }],
      }),
      ...question,
    ]);
  });

  it("can enter and leave full access without sending its notebook code", () => {
    const full = withNotebookContext(question, [], { sessionId: "session-1" });
    expect(full).toEqual([context({ sessionId: "session-1" }), ...question]);
    const read = withNotebookContext(question, [user(full)], initial);
    expect(read).toEqual(initialHistory()[0].parts);
    expect(
      withNotebookContext(question, [user(full), user(read)], {
        sessionId: "session-1",
      }),
    ).toEqual([context({ sessionId: "session-1" }), ...question]);
  });
});
