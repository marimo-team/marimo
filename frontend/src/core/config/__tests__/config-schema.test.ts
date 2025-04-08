/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { createStore } from "jotai";
import {
  AppConfigSchema,
  type UserConfig,
  UserConfigSchema,
} from "../config-schema";
import { resolvedMarimoConfigAtom } from "../config";
import { userConfigAtom } from "../config";
import { configOverridesAtom } from "../config";

test("default AppConfig", () => {
  const defaultConfig = AppConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "auto_download": [],
      "width": "medium",
      "sql_output": "auto",
    }
  `);
});

test("another AppConfig", () => {
  const config = AppConfigSchema.parse({
    width: "medium",
    app_title: null,
  });
  expect(config).toMatchInlineSnapshot(`
    {
      "app_title": null,
      "auto_download": [],
      "width": "medium",
    }
  `);
});

test("default UserConfig - empty", () => {
  const defaultConfig = UserConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "ai": {
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "copilot": false,
      },
      "display": {
        "cell_output": "above",
        "code_editor_font_size": 14,
        "dataframes": "rich",
        "default_width": "medium",
        "theme": "light",
      },
      "experimental": {},
      "formatting": {
        "line_length": 79,
      },
      "keymap": {
        "overrides": {},
        "preset": "default",
      },
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "on_cell_change": "autorun",
        "watcher_on_save": "lazy",
      },
      "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": false,
      },
      "server": {},
    }
  `);
});

test("default UserConfig - one level", () => {
  const defaultConfig = UserConfigSchema.parse({
    completion: {},
    save: {},
    formatting: {},
    keymap: {},
    runtime: {},
    display: {},
    experimental: {},
  });
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "ai": {
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "copilot": false,
      },
      "display": {
        "cell_output": "above",
        "code_editor_font_size": 14,
        "dataframes": "rich",
        "default_width": "medium",
        "theme": "light",
      },
      "experimental": {},
      "formatting": {
        "line_length": 79,
      },
      "keymap": {
        "overrides": {},
        "preset": "default",
      },
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "on_cell_change": "autorun",
        "watcher_on_save": "lazy",
      },
      "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": false,
      },
      "server": {},
    }
  `);

  expect(
    UserConfigSchema.parse({
      completion: {},
      save: {},
      formatting: {},
      keymap: {},
      runtime: {},
      display: {},
      experimental: {},
    }),
  ).toEqual(UserConfigSchema.parse({}));
});

test("default UserConfig with additional information", () => {
  const config = UserConfigSchema.parse({
    some_new_config: {
      is_new_config: true,
    },
  });
  expect(config).toEqual(
    expect.objectContaining({
      some_new_config: {
        is_new_config: true,
      },
    }),
  );
});

test("resolvedMarimoConfigAtom overrides correctly and does not mutate the original array", () => {
  const initialUserConfig = {
    completion: { activate_on_typing: true, copilot: false },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79 },
  };

  const overrides = {
    completion: { copilot: "github" },
    display: { theme: "dark" },
  };

  const store = createStore();

  store.set(userConfigAtom, initialUserConfig as UserConfig);
  store.set(configOverridesAtom, overrides);

  const result = store.get(resolvedMarimoConfigAtom);

  expect(result).toEqual({
    completion: { activate_on_typing: true, copilot: "github" },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79 },
    display: { theme: "dark" },
  });

  expect(initialUserConfig).toEqual({
    completion: { activate_on_typing: true, copilot: false },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79 },
  });
});
