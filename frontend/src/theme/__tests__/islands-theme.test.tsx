/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import { createStore } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { JsonOutput } from "@/components/editor/output/JsonOutput";
import {
  marimoDarkTheme,
  marimoLightTheme,
} from "@/components/editor/output/json-output/themes";
import { userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { StyleNamespace } from "../namespace";
import { resolvedThemeAtom } from "../useTheme";

let store: ReturnType<typeof createStore>;
let unsubscribe: (() => void) | undefined;
let media: EventTarget & { matches: boolean };

beforeEach(() => {
  vi.stubEnv("VITE_MARIMO_ISLANDS", "true");
  media = Object.assign(new EventTarget(), { matches: false });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => media),
  );
  store = createStore();
});

afterEach(() => {
  stopObserving();
  for (const element of [document.body, document.documentElement]) {
    for (const attribute of [
      "class",
      "style",
      "data-theme",
      "data-mode",
      "data-vscode-theme-kind",
    ]) {
      element.removeAttribute(attribute);
    }
  }
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function subscribe() {
  unsubscribe = store.sub(resolvedThemeAtom, vi.fn());
}

function stopObserving() {
  unsubscribe?.();
  unsubscribe = undefined;
}

function getTheme() {
  return store.get(resolvedThemeAtom);
}

function setSystemTheme(matches: boolean) {
  media.matches = matches;
  media.dispatchEvent(new Event("change"));
}

describe("islands host theme", () => {
  it("defaults to light on a transparent page even if the system is dark", () => {
    media.matches = true;
    subscribe();
    expect(getTheme()).toBe("light");
  });

  it.each(["body", "html"])(
    "follows %s theme attributes in both directions",
    async (tag) => {
      const host = document.querySelector(tag)!;
      subscribe();
      for (const [attribute, dark, light] of [
        ["class", "dark", "light"],
        ["class", "dark-mode", "light-mode"],
        ["class", "dark-theme", "light-theme"],
        ["data-theme", "dark", "light"],
        ["data-mode", "dark", "light"],
      ]) {
        host.setAttribute(attribute, dark);
        await expect.poll(getTheme).toBe("dark");
        host.setAttribute(attribute, light);
        await expect.poll(getTheme).toBe("light");
        host.removeAttribute(attribute);
      }
    },
  );

  it("reads the initial host theme and follows color-scheme changes", async () => {
    document.body.style.colorScheme = "dark";
    subscribe();
    expect(getTheme()).toBe("dark");
    document.body.style.colorScheme = "light";
    await expect.poll(getTheme).toBe("light");
    document.body.style.colorScheme = "dark";
    await expect.poll(getTheme).toBe("dark");
  });

  it("uses the background when color-scheme is normal", async () => {
    document.body.style.colorScheme = "normal";
    document.body.style.backgroundColor = "rgb(30, 30, 30)";
    subscribe();
    expect(getTheme()).toBe("dark");
    document.body.style.backgroundColor = "white";
    await expect.poll(getTheme).toBe("light");
  });

  it("resolves a host supporting both color schemes when the system changes", async () => {
    document.body.style.colorScheme = "light dark";
    subscribe();
    expect(getTheme()).toBe("light");
    for (const matches of [true, false]) {
      setSystemTheme(matches);
      await expect.poll(getTheme).toBe(matches ? "dark" : "light");
    }
  });

  it("shares a subscription, skips unchanged themes, and cleans up on unmount", async () => {
    const disconnect = vi.spyOn(MutationObserver.prototype, "disconnect");
    const removeListener = vi.spyOn(media, "removeEventListener");
    const listener = vi.fn();
    subscribe();
    const unsubscribeSecond = store.sub(resolvedThemeAtom, listener);
    document.body.classList.add("unrelated");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(listener).not.toHaveBeenCalled();
    unsubscribeSecond();
    expect(disconnect).not.toHaveBeenCalled();
    stopObserving();
    expect(disconnect).toHaveBeenCalledOnce();
    expect(removeListener).toHaveBeenCalledWith("change", expect.any(Function));
    document.body.classList.add("dark");
    subscribe();
    expect(getTheme()).toBe("dark");
  });

  it("ignores unrecognized theme attributes and transparent body backgrounds", async () => {
    document.body.dataset.theme = "custom-theme";
    document.body.dataset.mode = "auto";
    document.body.style.backgroundColor = "rgba(0, 0, 0, 0)";
    document.documentElement.style.backgroundColor = "white";
    subscribe();
    expect(getTheme()).toBe("light");
    document.documentElement.style.backgroundColor = "black";
    await expect.poll(getTheme).toBe("dark");
    document.documentElement.style.backgroundColor = "transparent";
    await expect.poll(getTheme).toBe("light");
  });

  it("falls back after a theme attribute is removed", async () => {
    document.body.dataset.theme = "dark";
    document.body.style.colorScheme = "light";
    subscribe();
    expect(getTheme()).toBe("dark");
    delete document.body.dataset.theme;
    await expect.poll(getTheme).toBe("light");
  });

  it("continues to observe the host without matchMedia", async () => {
    vi.stubGlobal("matchMedia", undefined);
    document.body.style.colorScheme = "light dark";
    subscribe();
    expect(getTheme()).toBe("light");
    document.body.style.colorScheme = "only dark";
    await expect.poll(getTheme).toBe("dark");
  });

  it.each(["light", "dark"] as const)(
    "does not override an explicit %s host when system preferences change",
    (theme) => {
      document.body.style.colorScheme = theme;
      subscribe();
      for (const matches of [true, false]) {
        setSystemTheme(matches);
        expect(getTheme()).toBe(theme);
      }
    },
  );

  it("re-reads host CSS when a media query changes its color-scheme", () => {
    const computedStyle = window.getComputedStyle(document.body);
    const scheme = vi.spyOn(computedStyle, "colorScheme", "get");
    vi.spyOn(window, "getComputedStyle").mockReturnValue(computedStyle);
    scheme.mockReturnValue("light");
    subscribe();
    expect(getTheme()).toBe("light");
    scheme.mockReturnValue("dark");
    media.dispatchEvent(new Event("change"));
    expect(getTheme()).toBe("dark");
  });

  it("discards queued mutations and media events after the last unsubscribe", async () => {
    const readStyle = vi.spyOn(window, "getComputedStyle");
    subscribe();
    document.body.style.colorScheme = "dark";
    stopObserving();
    readStyle.mockClear();
    media.dispatchEvent(new Event("change"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(readStyle).not.toHaveBeenCalled();
    subscribe();
    expect(getTheme()).toBe("dark");
  });

  it("keeps the VS Code override and returns to the host after it is removed", async () => {
    document.body.classList.add("dark");
    const { container, unmount } = render(
      <StyleNamespace>Widget</StyleNamespace>,
    );
    for (const [kind, theme] of [
      ["vscode-light", "light"],
      ["vscode-high-contrast", "dark"],
      ["vscode-light", "light"],
    ]) {
      document.body.dataset.vscodeThemeKind = kind;
      await waitFor(() => expect(container.firstChild).toHaveClass(theme));
    }
    delete document.body.dataset.vscodeThemeKind;
    await waitFor(() => expect(container.firstChild).toHaveClass("dark"));
    unmount();
  });

  it("does not subscribe to host themes outside Islands", async () => {
    vi.stubEnv("VITE_MARIMO_ISLANDS", "false");
    const config = defaultUserConfig();
    store.set(userConfigAtom, {
      ...config,
      display: { ...config.display, theme: "light" },
    });
    const observe = vi.spyOn(MutationObserver.prototype, "observe");
    const addListener = vi.spyOn(media, "addEventListener");
    subscribe();
    document.body.classList.add("dark");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(getTheme()).toBe("light");
    expect(observe).not.toHaveBeenCalled();
    expect(addListener).not.toHaveBeenCalled();
  });

  it("updates the namespace root used by shadow DOM widgets", async () => {
    const { container } = render(<StyleNamespace>Widget</StyleNamespace>);
    expect(container.firstChild).toHaveClass("marimo", "light");
    document.body.classList.add("dark");
    await waitFor(() =>
      expect(container.firstChild).toHaveClass("marimo", "dark"),
    );
    document.body.classList.remove("dark");
    await waitFor(() =>
      expect(container.firstChild).toHaveClass("marimo", "light"),
    );
  });

  it("updates the dictionary viewer palette without remounting", async () => {
    const { container } = render(
      <JsonOutput data={{ relu: 0, note: "text" }} />,
    );
    const viewer = container.querySelector<HTMLElement>(
      ".w-json-view-container",
    );
    expect(viewer).not.toBeNull();
    for (const theme of ["dark", "light"] as const) {
      document.body.dataset.theme = theme;
      const palette = theme === "dark" ? marimoDarkTheme : marimoLightTheme;
      await waitFor(() =>
        expect(viewer?.style.getPropertyValue("--w-rjv-color")).toBe(
          palette["--w-rjv-color"],
        ),
      );
    }
  });
});
