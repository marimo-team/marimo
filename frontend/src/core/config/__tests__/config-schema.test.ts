/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { AppConfigSchema, UserConfigSchema } from "../config-schema";

test("default AppConfig", () => {
  const defaultConfig = AppConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "width": "normal",
    }
  `);
});

test("default UserConfig", () => {
  const defaultConfig = UserConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "completion": {
        "activate_on_typing": true,
        "copilot": false,
      },
      "display": {
        "cell_output": "above",
        "code_editor_font_size": 14,
        "theme": "light",
      },
      "experimental": {},
      "formatting": {
        "line_length": 79,
      },
      "keymap": {
        "preset": "default",
      },
      "runtime": {
        "auto_instantiate": true,
      },
      "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": false,
      },
    }
  `);
});
