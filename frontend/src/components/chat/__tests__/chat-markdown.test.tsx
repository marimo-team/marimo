/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { ChatMarkdown } from "../chat-markdown";

const { aiAtom } = await vi.hoisted(async () => {
  const { atom } = await import("jotai");
  return {
    aiAtom: atom<{ mode?: "ask" | "manual" | "agent" | "code_mode" }>({}),
  };
});
vi.mock("@/core/config/config", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  aiAtom,
}));
vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: ({ value }: { value: string }) => (
    <pre>{value}</pre>
  ),
}));

it("updates snippet actions when switching between read-only and editing modes", async () => {
  const store = createStore();
  render(
    <Provider store={store}>
      <ChatMarkdown content={"```python\nx = 1\n```"} />
    </Provider>,
  );
  expect(
    await screen.findByRole("button", { name: "Add to Notebook" }),
  ).toBeInTheDocument();
  for (const mode of ["agent", "code_mode", "ask", "manual"] as const) {
    act(() => store.set(aiAtom, { mode }));
    expect(screen.getByRole("button", { name: /^Copy$/ })).toBeInTheDocument();
    expect(screen.getByText("x = 1")).toBeInTheDocument();
    const insertButton = screen.queryByRole("button", {
      name: "Add to Notebook",
    });
    expect(insertButton !== null).toBe(mode === "ask" || mode === "manual");
  }
});
