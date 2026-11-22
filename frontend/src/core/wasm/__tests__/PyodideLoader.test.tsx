/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, type PrimitiveAtom, Provider } from "jotai";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { toast } from "@/components/ui/use-toast";
import { Deferred } from "@/utils/Deferred";
import { reloadSafe } from "@/utils/reload-safe";
import { PyodideBridge } from "../bridge";
import { PyodideLoader } from "../PyodideLoader";

vi.mock("../bridge", () => ({
  PyodideBridge: { INSTANCE: {} },
}));
vi.mock("../utils", () => ({ isWasm: () => true }));
vi.mock("@/utils/reload-safe", () => ({ reloadSafe: vi.fn() }));
vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));
vi.mock("@/core/lifecycle/render-policy", async () => {
  const { atom } = await import("jotai");
  return { canPaintAtom: atom(false) };
});

let store: ReturnType<typeof createStore>;

beforeEach(() => {
  store = createStore();
  PyodideBridge.INSTANCE.initialized = new Deferred<void>();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function renderNotebook(canPaint = false) {
  const { canPaintAtom } = await vi.importMock<{
    canPaintAtom: PrimitiveAtom<boolean>;
  }>("@/core/lifecycle/render-policy");
  store.set(canPaintAtom, canPaint);
  return render(
    <Provider store={store}>
      <ErrorBoundary>
        <PyodideLoader>Notebook content</PyodideLoader>
      </ErrorBoundary>
    </Provider>,
  );
}

it("reloads after bootstrap failure instead of remounting with the rejected initialization promise", async () => {
  await renderNotebook();
  const initialized = PyodideBridge.INSTANCE.initialized;
  act(() => initialized.reject(new Error("Failed to fetch: HTTP 500")));

  const reload = await screen.findByRole("button", { name: "Reload page" });
  expect(screen.getByText("Failed to fetch: HTTP 500")).toBeVisible();
  fireEvent.click(reload);

  expect(reloadSafe).toHaveBeenCalledOnce();
  expect(PyodideBridge.INSTANCE.initialized).toBe(initialized);
  expect(screen.getByText("Something went wrong")).toBeVisible();
});

it("offers reload again if initialization also fails in a fresh page", async () => {
  const firstPage = await renderNotebook();
  act(() => PyodideBridge.INSTANCE.initialized.reject(new Error("HTTP 500")));
  fireEvent.click(await screen.findByRole("button", { name: "Reload page" }));
  firstPage.unmount();

  store = createStore();
  PyodideBridge.INSTANCE.initialized = new Deferred<void>();
  await renderNotebook();
  act(() => PyodideBridge.INSTANCE.initialized.reject(new Error("HTTP 500")));
  fireEvent.click(await screen.findByRole("button", { name: "Reload page" }));

  expect(reloadSafe).toHaveBeenCalledTimes(2);
  expect(screen.getByText("HTTP 500")).toBeVisible();
});

it("keeps paintable notebook content visible when bootstrap fails", async () => {
  await renderNotebook(true);
  act(() => PyodideBridge.INSTANCE.initialized.reject(new Error("HTTP 500")));

  await waitFor(() =>
    expect(toast).toHaveBeenCalledWith({
      title: "Failed to start the notebook runtime",
      description: "HTTP 500",
      variant: "danger",
    }),
  );
  expect(screen.getByText("Notebook content")).toBeVisible();
  expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  expect(reloadSafe).not.toHaveBeenCalled();
});
