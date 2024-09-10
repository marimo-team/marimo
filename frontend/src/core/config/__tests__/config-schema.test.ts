/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { AppConfigSchema, UserConfigSchema } from "../config-schema";

test("default AppConfig", () => {
  const defaultConfig = AppConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
  {
    "width": "medium",
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
      "content_font_size": "default",
      "width": "medium",
    }
  `);
});

test("default UserConfig - empty", () => {
  const defaultConfig = UserConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "ai": {},
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
        "add_script_metadata": false,
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "on_cell_change": "autorun",
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
      "ai": {},
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
        "add_script_metadata": false,
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "on_cell_change": "autorun",
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
