/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { type FC, useEffect, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppConfig } from "@/core/config/config-schema";
import { Deferred } from "@/utils/Deferred";

vi.mock("@/components/ui/toaster", () => ({ Toaster: () => null }));
vi.mock("@/components/editor/TracebackModalContainer", () => ({
  TracebackModalContainer: () => null,
}));

describe("MarimoApp read-page loading", () => {
  let pageModule: Deferred<{ default: FC<{ appConfig: AppConfig }> }>;
  const mounted = vi.fn();
  const unmounted = vi.fn();

  const RunPage: FC<{ appConfig: AppConfig }> = ({ appConfig }) => {
    const [count, setCount] = useState(0);
    useEffect(() => {
      mounted();
      return unmounted;
    }, []);
    return (
      <button type="button" onClick={() => setCount((value) => value + 1)}>
        {appConfig.width}: {count}
      </button>
    );
  };

  beforeEach(() => {
    vi.resetModules();
    pageModule = new Deferred();
    vi.doMock("@/components/pages/run-page", () => pageModule.promise);
  });

  afterEach(() => {
    vi.doUnmock("@/components/pages/run-page");
    vi.restoreAllMocks();
  });

  async function setup() {
    const { store } = await import("@/core/state/jotai");
    const { initialModeAtom } = await import("@/core/mode");
    const { appConfigAtom } = await import("@/core/config/config");
    const { MarimoApp, preloadPage } = await import("../MarimoApp");
    store.set(initialModeAtom, "read");
    return {
      store,
      appConfigAtom,
      preloadPage,
      element: (
        <Provider store={store}>
          <MarimoApp />
        </Provider>
      ),
    };
  }

  it("keeps the shell mounted while loading and preserves the page on config updates", async () => {
    const { element, store, appConfigAtom, preloadPage } = await setup();
    preloadPage("read");
    const { container } = render(element);

    expect(container.querySelector(".contents")).toBeVisible();
    expect(mounted).not.toHaveBeenCalled();

    await act(async () => pageModule.resolve({ default: RunPage }));
    fireEvent.click(await screen.findByRole("button", { name: "medium: 0" }));
    expect(screen.getByRole("button", { name: "medium: 1" })).toBeVisible();

    act(() => {
      preloadPage("read");
      store.set(appConfigAtom, { ...store.get(appConfigAtom), width: "full" });
    });
    expect(screen.getByRole("button", { name: "full: 1" })).toBeVisible();
    expect(mounted).toHaveBeenCalledExactlyOnceWith();
    expect(unmounted).not.toHaveBeenCalled();
  });

  it("renders a page whose import has already completed", async () => {
    const { element, preloadPage } = await setup();
    preloadPage("read");
    pageModule.resolve({ default: RunPage });
    await import("@/components/pages/run-page");

    render(element);
    expect(
      await screen.findByRole("button", { name: "medium: 0" }),
    ).toBeVisible();
    expect(mounted).toHaveBeenCalledExactlyOnceWith();
  });

  it("reports a failed preload through the existing error boundary", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { element, preloadPage } = await setup();
    preloadPage("read");
    render(element);

    await act(async () =>
      pageModule.reject(new Error("read page unavailable")),
    );

    expect(
      await screen.findByRole("heading", { name: "Something went wrong" }),
    ).toBeVisible();
    expect(mounted).not.toHaveBeenCalled();
  });

  it("does not mount the page if its import completes after unmounting", async () => {
    const { element, preloadPage } = await setup();
    preloadPage("read");
    const { unmount } = render(element);
    unmount();

    await act(async () => pageModule.resolve({ default: RunPage }));

    expect(mounted).not.toHaveBeenCalled();
  });
});
