/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { expect, test } from "vitest";
import { userConfigAtom } from "../../config/config";
import { defaultUserConfig } from "../../config/config-schema";

test("set-theme message updates userConfigAtom", () => {
  const store = createStore();

  // Initialize with default config
  store.set(userConfigAtom, defaultUserConfig());

  // Simulate receiving a set-theme message
  store.set(userConfigAtom, (prev) => ({
    ...prev,
    display: {
      ...prev.display,
      theme: "dark",
    },
  }));

  const config = store.get(userConfigAtom);
  expect(config.display.theme).toBe("dark");
});

test("set-theme preserves other config values", () => {
  const store = createStore();

  const customConfig = {
    ...defaultUserConfig(),
    display: {
      ...defaultUserConfig().display,
      code_editor_font_size: 16,
      theme: "light",
    },
  };

  store.set(userConfigAtom, customConfig);

  // Simulate receiving a set-theme message
  store.set(userConfigAtom, (prev) => ({
    ...prev,
    display: {
      ...prev.display,
      theme: "dark",
    },
  }));

  const config = store.get(userConfigAtom);
  expect(config.display.theme).toBe("dark");
  expect(config.display.code_editor_font_size).toBe(16);
});

test("set-theme can toggle between light and dark", () => {
  const store = createStore();

  store.set(userConfigAtom, defaultUserConfig());

  // Toggle to dark
  store.set(userConfigAtom, (prev) => ({
    ...prev,
    display: {
      ...prev.display,
      theme: "dark",
    },
  }));

  expect(store.get(userConfigAtom).display.theme).toBe("dark");

  // Toggle back to light
  store.set(userConfigAtom, (prev) => ({
    ...prev,
    display: {
      ...prev.display,
      theme: "light",
    },
  }));

  expect(store.get(userConfigAtom).display.theme).toBe("light");
});
