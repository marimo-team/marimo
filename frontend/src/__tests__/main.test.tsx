/* Copyright 2024 Marimo. All rights reserved. */
import { mount, visibleForTesting } from "../mount";
import { store } from "../core/state/jotai";
import { type AppMode, viewStateAtom } from "../core/mode";
import { codeAtom, filenameAtom } from "../core/saving/file-state";
import { showCodeInRunModeAtom, marimoVersionAtom } from "../core/meta/state";
import {
  appConfigAtom,
  userConfigAtom,
  configOverridesAtom,
} from "../core/config/config";
import { describe, beforeEach, it, expect, vi } from "vitest";
import {
  type AppConfig,
  parseAppConfig,
  parseUserConfig,
} from "@/core/config/config-schema";

vi.mock("../utils/vitals", () => ({
  reportVitals: vi.fn(),
}));

describe("main", () => {
  beforeEach(() => {
    visibleForTesting.reset();

    // Reset store before each test
    store.set(viewStateAtom, { mode: "not-set" as AppMode, cellAnchor: null });
    store.set(codeAtom, undefined);
    store.set(filenameAtom, null);
    store.set(showCodeInRunModeAtom, false);
    store.set(marimoVersionAtom, "unknown");
    store.set(appConfigAtom, parseAppConfig({}));
    store.set(userConfigAtom, parseUserConfig({}));
    store.set(configOverridesAtom, {});
  });

  it.each(["edit", "read", "home", "run"])(
    "should mount with mode %s",
    (mode) => {
      const el = document.createElement("div");
      mount({ mode: "edit" }, el);

      expect(store.get(viewStateAtom).mode).toBe("edit");
      expect(store.get(filenameAtom)).toBeDefined();
      expect(store.get(marimoVersionAtom)).toBe("unknown");
      expect(store.get(showCodeInRunModeAtom)).toBe(true);
    },
  );

  it("should not mount with invalid mode", () => {
    const el = document.createElement("div");
    const error = mount({ mode: "invalid" }, el);
    expect(error).toBeDefined();
    expect(error?.message).toBe("Invalid marimo mount options");
  });

  it("should mount with null values", () => {
    const el = document.createElement("div");
    const error = mount(
      { mode: "edit", filename: null, code: null, version: null },
      el,
    );
    expect(error).toBeUndefined();

    mount({ mode: "edit", filename: null, code: null, version: null }, el);
    expect(store.get(filenameAtom)).toBeNull();
    expect(store.get(codeAtom)).toBe("");
    expect(store.get(marimoVersionAtom)).toBe("unknown");
    expect(store.get(viewStateAtom).mode).toBe("edit");
  });

  it("should mount with undefined values", () => {
    const el = document.createElement("div");
    const error = mount(
      {
        mode: "edit",
        filename: undefined,
        code: undefined,
        version: undefined,
      },
      el,
    );
    expect(error).toBeUndefined();

    expect(store.get(filenameAtom)).toBeNull();
    expect(store.get(codeAtom)).toBe("");
    expect(store.get(marimoVersionAtom)).toBe("unknown");
    expect(store.get(viewStateAtom).mode).toBe("edit");
  });

  it("should mount with empty config", () => {
    const el = document.createElement("div");
    const error = mount(
      { mode: "edit", config: {}, configOverrides: {}, appConfig: {} },
      el,
    );
    expect(error).toBeUndefined();
    expect(store.get(userConfigAtom)).toEqual(parseUserConfig({}));
    expect(store.get(configOverridesAtom)).toEqual({});
    expect(store.get(appConfigAtom)).toEqual(parseAppConfig({}));
    expect(store.get(viewStateAtom).mode).toBe("edit");
    expect(store.get(showCodeInRunModeAtom)).toBe(true);
  });

  it("should mount with all options", () => {
    const el = document.createElement("div");
    const options = {
      filename: "test.py",
      code: "print('hello')",
      version: "1.0.0",
      mode: "edit" as const,
      config: {
        display: {
          cell_output: "above",
          code_editor_font_size: 99,
          dataframes: "rich",
          default_table_page_size: 10,
          default_width: "medium",
          theme: "light",
        },
      },
      configOverrides: { display: { code_editor_font_size: 100 } },
      appConfig: { app_title: "My App" } as AppConfig,
      view: { showAppCode: true },
    };

    mount(options, el);

    expect(store.get(filenameAtom)).toBe("test.py");
    expect(store.get(codeAtom)).toBe("print('hello')");
    expect(store.get(marimoVersionAtom)).toBe("1.0.0");
    expect(store.get(viewStateAtom).mode).toBe("edit");
    expect(store.get(showCodeInRunModeAtom)).toBe(true);
    expect(store.get(userConfigAtom).display).toEqual(
      expect.objectContaining({
        code_editor_font_size: 99,
      }),
    );
    expect(store.get(configOverridesAtom)).toEqual(
      expect.objectContaining({
        display: { code_editor_font_size: 100 },
      }),
    );
    expect(store.get(appConfigAtom)).toEqual(
      expect.objectContaining({ app_title: "My App" }),
    );
  });

  it("should throw on invalid options", () => {
    const el = document.createElement("div");
    const error = mount({ invalid: true } as unknown, el);
    expect(error).toBeDefined();
    expect(error?.message).toBe("Invalid marimo mount options");
  });

  it("should not mount twice", () => {
    const el = document.createElement("div");
    mount({ mode: "edit" }, el);
    const error = mount({ mode: "edit" }, el);
    expect(error).toBeDefined();
    expect(error?.message).toBe("marimo app has already been mounted.");
  });
});
