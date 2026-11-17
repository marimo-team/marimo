/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { SessionTabs } from "../session-tabs";
import { addSession, agentSessionStateAtom } from "../state";

vi.mock("../agent-selector", () => ({ AgentSelector: () => null }));

it("keeps session selection and close as separate named buttons", () => {
  const first = addSession(
    { sessions: [], activeTabId: null },
    { agentId: "claude", firstMessage: "First" },
  ).sessions[0];
  const second = addSession(
    { sessions: [], activeTabId: null },
    { agentId: "codex", firstMessage: "Second" },
  ).sessions[0];
  const store = createStore();
  store.set(agentSessionStateAtom, {
    sessions: [first, second],
    activeTabId: first.tabId,
  });
  render(
    <Provider store={store}>
      <SessionTabs />
    </Provider>,
  );
  const select = screen.getByRole("button", {
    name: /Second$/,
    pressed: false,
  });
  select.focus();
  expect(select).toHaveFocus();
  fireEvent.click(select);
  expect(select).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "Close First" }));
  expect(store.get(agentSessionStateAtom).activeTabId).toBe(second.tabId);
  expect(
    store.get(agentSessionStateAtom).sessions.map((session) => session.title),
  ).toEqual(["Second"]);
});
