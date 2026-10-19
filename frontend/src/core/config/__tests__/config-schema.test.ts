/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { Logger } from "@/utils/Logger";
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
  parseConfigOverrides,
  parseUserConfig,
  type UserConfig,
  UserConfigSchema,
} from "../config-schema";

describe("configuration loading", () => {
  beforeEach(() => {
    vi.spyOn(Logger, "warn").mockImplementation(vi.fn());
    vi.spyOn(Logger, "log").mockImplementation(vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("recovers invalid fields without discarding valid settings or mutating input", () => {
    const input = {
      keymap: {
        preset: "helix",
        overrides: { "run-cell": "Ctrl-Enter" },
        destructive_delete: false,
      },
      display: { theme: "dark" },
      save: { autosave: "off" },
      future_section: { enabled: true },
    };
    const original = structuredClone(input);

    expect(parseUserConfig(input)).toEqual(
      mergeConfig(defaultUserConfig(), input, {
        keymap: { preset: "default" },
      }),
    );
    expect(input).toEqual(original);
    expect(Logger.warn).toHaveBeenCalledWith(
      expect.stringContaining("keymap.preset"),
    );
  });

  test("recovers malformed sections and multiple invalid fields", () => {
    expect(
      parseUserConfig({
        keymap: null,
        display: { theme: "dark", code_editor_font_size: -1 },
        save: { autosave: "invalid", autosave_delay: 5000 },
        ai: { max_tokens: -1, rules: "Keep answers short" },
      }),
    ).toEqual(
      mergeConfig(defaultUserConfig(), {
        display: { theme: "dark" },
        save: { autosave_delay: 5000 },
        ai: { rules: "Keep answers short" },
      }),
    );
  });

  test("discards invalid array settings instead of leaving malformed entries", () => {
    expect(
      parseUserConfig({
        file_browser: { folders: [{ name: "Missing path" }] },
        runtime: {
          default_auto_download: ["html", "invalid"],
          on_cell_change: "lazy",
        },
      }),
    ).toEqual(
      mergeConfig(defaultUserConfig(), {
        runtime: { on_cell_change: "lazy" },
      }),
    );
  });

  test.each([null, [], "vim", 42])(
    "recovers malformed root config: %j",
    (input) => {
      expect(parseUserConfig(input)).toEqual(defaultUserConfig());
      expect(parseConfigOverrides(input)).toEqual({});
    },
  );

  test("keeps strict validation for the settings form", () => {
    expect(
      UserConfigSchema.safeParse({ keymap: { preset: "helix" } }).success,
    ).toBe(false);
  });

  test("preserves sparse overrides, transformations, and unknown keys", () => {
    const input = {
      completion: { copilot: true, future_option: "enabled" },
      display: { default_width: "normal" },
      save: { autosave_delay: 100 },
      ai: {
        models: { chat_model: "custom/model", future_option: true },
      },
      file_browser: { folders: [{ path: "/data", future_option: true }] },
      future_section: { enabled: true },
    };

    expect(parseConfigOverrides(input)).toEqual({
      ...input,
      completion: { copilot: "github", future_option: "enabled" },
      display: { default_width: "compact" },
      save: { autosave_delay: 1000 },
    });
    expect(parseConfigOverrides({})).toEqual({});
    expect(parseConfigOverrides(undefined)).toEqual({});
    expect(parseConfigOverrides({ display: { theme: undefined } })).toEqual({
      display: {},
    });
  });

  test("invalid overrides preserve lower-priority user settings", () => {
    const userConfig = parseUserConfig({
      keymap: { preset: "vim", overrides: { "run-cell": "Ctrl-Enter" } },
      display: { theme: "dark", code_editor_font_size: 18 },
      file_browser: { folders: [{ path: "/data" }] },
    });
    const input = {
      keymap: { preset: "helix", overrides: { "run-cell": 42 } },
      display: { theme: "light" },
      file_browser: { folders: [{ name: "Missing path" }] },
      save: null,
    };
    const original = structuredClone(input);
    const overrides = parseConfigOverrides(input);

    expect(overrides).toEqual({
      keymap: { overrides: {} },
      display: { theme: "light" },
      file_browser: {},
    });
    expect(mergeConfig(userConfig, overrides)).toEqual(
      mergeConfig(userConfig, { display: { theme: "light" } }),
    );
    expect(input).toEqual(original);
  });
});

test("default AppConfig", () => {
  const defaultConfig = AppConfigSchema.parse({});
  expect(defaultConfig).toMatchInlineSnapshot(`
    {
      "auto_download": [],
      "sql_output": "auto",
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
        "mode": "manual",
        "models": {
          "custom_models": [],
          "displayed_models": [],
        },
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "auto_close_pairs": true,
        "copilot": false,
        "signature_hint_on_typing": false,
      },
      "diagnostics": {},
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
      "experimental": {},
      "file_browser": {},
      "formatting": {
        "line_length": 79,
      },
      "keymap": {
        "destructive_delete": true,
        "overrides": {},
        "preset": "default",
      },
      "mcp": {},
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "default_auto_download": [],
        "default_sql_output": "auto",
        "on_cell_change": "autorun",
        "reactive_tests": true,
        "show_tracebacks": false,
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
        "allow_provider_config": true,
        "custom_providers": {},
        "enabled": true,
        "inline_tooltip": false,
        "mode": "manual",
        "models": {
          "custom_models": [],
          "displayed_models": [],
        },
        "rules": "",
      },
      "completion": {
        "activate_on_typing": true,
        "auto_close_pairs": true,
        "copilot": false,
        "signature_hint_on_typing": false,
      },
      "diagnostics": {},
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
      "experimental": {},
      "file_browser": {},
      "formatting": {
        "line_length": 79,
      },
      "keymap": {
        "destructive_delete": true,
        "overrides": {},
        "preset": "default",
      },
      "mcp": {},
      "package_management": {
        "manager": "pip",
      },
      "runtime": {
        "auto_instantiate": true,
        "auto_reload": "off",
        "default_auto_download": [],
        "default_sql_output": "auto",
        "on_cell_change": "autorun",
        "reactive_tests": true,
        "show_tracebacks": false,
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
    { path: "/shared" },
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
    formatting: { line_length: 79 },
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
    formatting: { line_length: 79 },
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
