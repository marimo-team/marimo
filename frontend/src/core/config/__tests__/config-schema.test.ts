/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { expect, test } from "vitest";
import {
  configOverridesAtom,
  connectionTransportTypeAtom,
  mergeConfig,
  resolvedMarimoConfigAtom,
  userConfigAtom,
} from "../config";
import {
  AppConfigSchema,
  defaultUserConfig,
  type UserConfig,
  UserConfigSchema,
} from "../config-schema";

test("legacy Manual config resolves to Read only", () => {
  const config = UserConfigSchema.parse({ ai: { mode: "manual" } });
  expect(config).toEqual(UserConfigSchema.parse({ ai: { mode: "ask" } }));
});

test("default AppConfig", () => {
  const defaultConfig = AppConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "auto_download": [],
      "sql_output": "auto",
      "width": "compact",
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
      "sql_output": "auto",
      "width": "medium",
    }
  `);
});

test("default UserConfig - empty", () => {
  const defaultConfig = defaultUserConfig();
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "ai": {
        "allow_provider_config": true,
        "custom_providers": {},
        "enabled": true,
        "inline_tooltip": false,
        "max_tokens": null,
        "mode": "ask",
        "models": {
          "autocomplete_model": null,
          "chat_model": null,
          "custom_models": [],
          "displayed_models": [],
          "edit_model": null,
        },
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "auto_close_pairs": true,
        "copilot": false,
        "signature_hint_on_typing": false,
      },
      "diagnostics": {
        "sql_linter": true,
      },
      "display": {
        "cell_output": "below",
        "code_editor_font_size": 14,
        "code_lens": true,
        "dataframes": "rich",
        "default_table_max_columns": 50,
        "default_table_page_size": 10,
        "default_width": "medium",
        "reference_highlighting": true,
        "theme": "light",
      },
      "experimental": {
        "debugger": false,
        "execution_type": "relaxed",
        "isolate_apps": false,
        "line_timing": false,
      },
      "file_browser": null,
      "formatting": {
        "infer_types": "off",
        "line_length": 79,
      },
      "keymap": {
        "destructive_delete": true,
        "overrides": {},
        "preset": "default",
      },
      "language_servers": {
        "pylsp": {
          "enable_flake8": false,
          "enable_mypy": true,
          "enable_pydocstyle": false,
          "enable_pyflakes": false,
          "enable_pylint": false,
          "enable_ruff": true,
          "enabled": false,
        },
      },
      "mcp": {
        "mcpServers": {},
        "presets": [],
      },
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "cache_cells": false,
        "default_auto_download": [],
        "default_sql_output": "auto",
        "on_cell_change": "autorun",
        "pin_modules": true,
        "pythonpath": [],
        "reactive_tests": true,
        "serve_cached_sessions_in_apps": false,
        "show_tracebacks": false,
        "watcher_on_save": "lazy",
      },
      "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": false,
      },
      "server": {
        "disable_file_downloads": false,
        "session_secret": null,
      },
      "sharing": null,
      "snippets": {
        "custom_paths": [],
        "include_default_snippets": true,
      },
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
        "allow_provider_config": true,
        "custom_providers": {},
        "enabled": true,
        "inline_tooltip": false,
        "max_tokens": null,
        "mode": "ask",
        "models": {
          "autocomplete_model": null,
          "chat_model": null,
          "custom_models": [],
          "displayed_models": [],
          "edit_model": null,
        },
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "auto_close_pairs": true,
        "copilot": false,
        "signature_hint_on_typing": false,
      },
      "diagnostics": {
        "sql_linter": true,
      },
      "display": {
        "cell_output": "below",
        "code_editor_font_size": 14,
        "code_lens": true,
        "dataframes": "rich",
        "default_table_max_columns": 50,
        "default_table_page_size": 10,
        "default_width": "medium",
        "reference_highlighting": true,
        "theme": "light",
      },
      "experimental": {
        "debugger": false,
        "execution_type": "relaxed",
        "isolate_apps": false,
        "line_timing": false,
      },
      "file_browser": null,
      "formatting": {
        "infer_types": "off",
        "line_length": 79,
      },
      "keymap": {
        "destructive_delete": true,
        "overrides": {},
        "preset": "default",
      },
      "language_servers": {
        "pylsp": {
          "enable_flake8": false,
          "enable_mypy": true,
          "enable_pydocstyle": false,
          "enable_pyflakes": false,
          "enable_pylint": false,
          "enable_ruff": true,
          "enabled": false,
        },
      },
      "mcp": {
        "mcpServers": {},
        "presets": [],
      },
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "cache_cells": false,
        "default_auto_download": [],
        "default_sql_output": "auto",
        "on_cell_change": "autorun",
        "pin_modules": true,
        "pythonpath": [],
        "reactive_tests": true,
        "serve_cached_sessions_in_apps": false,
        "show_tracebacks": false,
        "watcher_on_save": "lazy",
      },
      "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": false,
      },
      "server": {
        "disable_file_downloads": false,
        "session_secret": null,
      },
      "sharing": null,
      "snippets": {
        "custom_paths": [],
        "include_default_snippets": true,
      },
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
      diagnostics: {},
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

test("UserConfig with file browser folders", () => {
  const config = UserConfigSchema.parse({
    file_browser: {
      folders: [{ path: "/data", name: "Data" }, { path: "/shared" }],
    },
  });

  expect(config.file_browser?.folders).toEqual([
    { path: "/data", name: "Data" },
    { path: "/shared", name: null },
  ]);
});

test("UserConfig with custom_providers", () => {
  const config = UserConfigSchema.parse({
    ai: {
      custom_providers: {
        my_provider: {
          api_key: "test-key",
          base_url: "https://api.example.com/v1",
        },
        another_provider: {
          base_url: "https://api.another.com/v1",
        },
      },
    },
  });

  expect(config.ai?.custom_providers).toEqual({
    my_provider: {
      api_key: "test-key",
      base_url: "https://api.example.com/v1",
    },
    another_provider: {
      base_url: "https://api.another.com/v1",
    },
  });
});

test("UserConfig custom_providers defaults to empty object", () => {
  const config = UserConfigSchema.parse({
    ai: {},
  });

  expect(config.ai?.custom_providers).toEqual({});
});

test("resolvedMarimoConfigAtom overrides correctly and does not mutate the original array", () => {
  const initialUserConfig = {
    completion: {
      activate_on_typing: true,
      copilot: false,
      signature_hint_on_typing: false,
    },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79, infer_types: "off" },
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
    completion: {
      activate_on_typing: true,
      copilot: "github",
      signature_hint_on_typing: false,
    },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79, infer_types: "off" },
    display: { theme: "dark" },
  });

  expect(initialUserConfig).toEqual({
    completion: {
      activate_on_typing: true,
      copilot: false,
      signature_hint_on_typing: false,
    },
    save: {
      autosave: "after_delay",
      autosave_delay: 1000,
      format_on_save: false,
    },
    formatting: { line_length: 79, infer_types: "off" },
  });
});

test("connectionTransportTypeAtom defaults to websocket", () => {
  const store = createStore();
  store.set(userConfigAtom, defaultUserConfig());
  expect(store.get(connectionTransportTypeAtom)).toBe("websocket");
});

test("connectionTransportTypeAtom reads server.transport", () => {
  const store = createStore();
  const config = defaultUserConfig();
  store.set(userConfigAtom, {
    ...config,
    server: { ...config.server, transport: "sse" },
  });
  expect(store.get(connectionTransportTypeAtom)).toBe("sse");
});

test("mergeConfig replaces arrays instead of merging by index", () => {
  const prev = {
    ai: {
      models: {
        displayed_models: ["wandb/a", "wandb/b", "wandb/c"],
        custom_models: ["wandb/custom"],
      },
    },
  };
  const patch = {
    ai: {
      models: {
        displayed_models: ["wandb/a"],
        custom_models: [],
      },
    },
  };

  expect(mergeConfig(prev, patch)).toEqual({
    ai: {
      models: {
        displayed_models: ["wandb/a"],
        custom_models: [],
      },
    },
  });
});

test.each([{}, { "run-cell": "Alt-Enter" }])(
  "mergeConfig replaces shortcut dictionaries with %j",
  (overrides) => {
    const original = {
      keymap: {
        preset: "vim",
        overrides: { "run-all": "Ctrl-Enter" },
      },
    };
    expect(mergeConfig(original, { keymap: { overrides } })).toEqual({
      keymap: { preset: "vim", overrides },
    });
    expect(original.keymap.overrides).toEqual({ "run-all": "Ctrl-Enter" });
  },
);

test.each(["ai.custom_providers", "signing.trusted_signers"])(
  "mergeConfig replaces records at %s while preserving retained record fields",
  (path) => {
    const [section, name] = path.split(".");
    const original = {
      [section]: {
        [name]: {
          retained: { name: "before", api_key: "secret" },
          removed: { name: "removed" },
        },
      },
    };
    expect(
      mergeConfig(original, {
        [section]: { [name]: { retained: { name: "after" } } },
      }),
    ).toEqual({
      [section]: {
        [name]: { retained: { name: "after", api_key: "secret" } },
      },
    });
    expect(mergeConfig(original, { [section]: { [name]: {} } })).toEqual({
      [section]: { [name]: {} },
    });
  },
);
