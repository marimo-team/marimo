/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { type FC, StrictMode, useEffect, useState } from "react";
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
    const { pageAppConfigAtom } = await import("@/core/config/config");
    const { MarimoApp, preloadPage } = await import("../MarimoApp");
    store.set(initialModeAtom, "read");
    return {
      store,
      pageAppConfigAtom,
      preloadPage,
      element: (
        <Provider store={store}>
          <MarimoApp />
        </Provider>
      ),
    };
  }

  function resolvePage() {
    return act(async () => pageModule.resolve({ default: RunPage }));
  }

  function rejectPage() {
    return act(async () => {
      pageModule.reject(new Error("read page unavailable"));
      // Cross an event-loop turn so an unhandled rejection would reach Vitest.
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  it("keeps the shell mounted while loading and preserves the page on config updates", async () => {
    const { element, store, pageAppConfigAtom, preloadPage } = await setup();
    preloadPage("read");
    const { container } = render(element);

    expect(container.querySelector(".contents")).toBeVisible();
    expect(mounted).not.toHaveBeenCalled();

    await resolvePage();
    fireEvent.click(await screen.findByRole("button", { name: "compact: 0" }));
    expect(screen.getByRole("button", { name: "compact: 1" })).toBeVisible();

    act(() => {
      preloadPage("read");
      store.set(pageAppConfigAtom, { width: "full" });
    });
    expect(screen.getByRole("button", { name: "full: 1" })).toBeVisible();
    expect(mounted).toHaveBeenCalledExactlyOnceWith();
    expect(unmounted).not.toHaveBeenCalled();
  });

  it("renders an already-preloaded page on the first commit", async () => {
    const { element, preloadPage } = await setup();
    preloadPage("read");
    pageModule.resolve({ default: RunPage });
    await import("@/components/pages/run-page");

    render(element);
    expect(screen.getByRole("button", { name: "compact: 0" })).toBeVisible();
    expect(mounted).toHaveBeenCalledExactlyOnceWith();
  });

  it("loads without an explicit preload under StrictMode", async () => {
    const { element } = await setup();
    render(<StrictMode>{element}</StrictMode>);

    await resolvePage();
    fireEvent.click(await screen.findByRole("button", { name: "compact: 0" }));
    expect(screen.getByRole("button", { name: "compact: 1" })).toBeVisible();
  });

  it.each(["before", "after"] as const)(
    "reports a preload that failed %s mounting through the error boundary",
    async (timing) => {
      vi.spyOn(console, "error").mockImplementation(() => undefined);
      const { element, preloadPage } = await setup();
      preloadPage("read");
      if (timing === "after") {
        render(element);
      }

      await rejectPage();

      if (timing === "before") {
        render(element);
      }
      expect(
        await screen.findByRole("heading", { name: "Something went wrong" }),
      ).toBeVisible();
      expect(mounted).not.toHaveBeenCalled();
    },
  );

  it("does not mount the page if its import completes after unmounting", async () => {
    const { element, preloadPage } = await setup();
    preloadPage("read");
    const { unmount } = render(element);
    unmount();

    await resolvePage();

    expect(mounted).not.toHaveBeenCalled();
  });
});
