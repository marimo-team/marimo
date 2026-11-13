/* Copyright 2026 Marimo. All rights reserved. */
import { z } from "zod";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import type { MarimoConfig, schemas } from "../network/types";

// This has to be defined in the same file as the zod schema to satisfy zod
export const PackageManagerNames = [
  "pip",
  "uv",
  "rye",
  "poetry",
  "pixi",
] as const;
export type PackageManagerName = (typeof PackageManagerNames)[number];

/**
 * normal == compact, but normal is deprecated
 */
const VALID_APP_WIDTHS = [
  "normal",
  "compact",
  "medium",
  "full",
  "columns",
] as const;

/**
 * SQL output formats
 */
const VALID_SQL_OUTPUT_FORMATS = [
  "auto",
  "native",
  "polars",
  "lazy-polars",
  "pandas",
] as const;
export type SqlOutputType = (typeof VALID_SQL_OUTPUT_FORMATS)[number];

export const DEFAULT_AI_MODEL = "openai/gpt-4o";

/**
 * Export types for auto download
 */
const AUTO_DOWNLOAD_FORMATS = ["html", "markdown", "ipynb"] as const;

export const TYPE_INFERENCE_MODES = ["off", "jedi"] as const;

export type CopilotMode = NonNullable<schemas["AiConfig"]["mode"]>;
export const COPILOT_MODES: CopilotMode[] = [
  "manual",
  "ask",
  "agent",
  "code_mode",
];

const AiConfigSchema = z
  .object({
    api_key: z.string().optional(),
    base_url: z.string().optional(),
    project: z.string().optional(),
  })
  .loose();

const AiModelsSchema = z.object({
  chat_model: z.string().nullish().prefault(null),
  edit_model: z.string().nullish().prefault(null),
  autocomplete_model: z.string().nullish().prefault(null),
  displayed_models: z.array(z.string()).default([]),
  custom_models: z.array(z.string()).default([]),
});

// Extract the model key type from the schema
export type AIModelKey = keyof Pick<
  z.infer<typeof AiModelsSchema>,
  "chat_model" | "edit_model" | "autocomplete_model"
>;

export const UserConfigSchema = z
  .looseObject({
    completion: z
      .object({
        activate_on_typing: z.boolean().prefault(true),
        signature_hint_on_typing: z.boolean().prefault(false),
        auto_close_pairs: z.boolean().prefault(true),
        copilot: z
          .union([z.boolean(), z.enum(["github", "codeium", "custom"])])
          .prefault(false)
          .transform((copilot) => {
            if (copilot === true) {
              return "github";
            }
            return copilot;
          }),
        codeium_api_key: z.string().nullish(),
      })
      .prefault({}),
    save: z
      .looseObject({
        autosave: z.enum(["off", "after_delay"]).prefault("after_delay"),
        autosave_delay: z
          .number()
          .nonnegative()
          // Ensure that the delay is at least 1 second
          .transform((millis) => Math.max(millis, 1000))
          .prefault(1000),
        format_on_save: z.boolean().prefault(false),
      })
      .prefault({}),
    formatting: z
      .looseObject({
        line_length: z
          .number()
          .nonnegative()
          .prefault(79)
          .transform((n) => Math.min(n, 1000)),
        infer_types: z.enum(TYPE_INFERENCE_MODES).prefault("off"),
      })
      .prefault({}),
    keymap: z
      .looseObject({
        preset: z.enum(["default", "vim"]).prefault("default"),
        overrides: z.record(z.string(), z.string()).prefault({}),
        destructive_delete: z.boolean().prefault(true),
      })
      .prefault({}),
    runtime: z
      .looseObject({
        auto_instantiate: z.boolean().prefault(true),
        on_cell_change: z.enum(["lazy", "autorun"]).prefault("autorun"),
        auto_reload: z.enum(["off", "lazy", "autorun"]).prefault("off"),
        reactive_tests: z.boolean().prefault(true),
        watcher_on_save: z.enum(["lazy", "autorun"]).prefault("lazy"),
        sql_default_limit: z.number().int().nullable().optional(),
        default_sql_output: z.enum(VALID_SQL_OUTPUT_FORMATS).prefault("auto"),
        default_auto_download: z
          .array(z.enum(AUTO_DOWNLOAD_FORMATS))
          .prefault([]),
        show_tracebacks: z.boolean().prefault(false),
        pythonpath: z.array(z.string()).prefault([]),
        cache_cells: z.boolean().prefault(false),
        pin_modules: z.boolean().prefault(true),
        serve_cached_sessions_in_apps: z.boolean().prefault(false),
      })
      .prefault({}),
    display: z
      .looseObject({
        theme: z.enum(["light", "dark", "system"]).prefault("light"),
        code_editor_font_size: z.number().nonnegative().prefault(14),
        cell_output: z.enum(["above", "below"]).prefault("below"),
        dataframes: z.enum(["rich", "plain"]).prefault("rich"),
        default_table_page_size: z.number().prefault(10),
        default_table_max_columns: z.number().prefault(50),
        default_width: z
          .enum(VALID_APP_WIDTHS)
          .prefault("medium")
          .transform((width) => {
            if (width === "normal") {
              return "compact";
            }
            return width;
          }),
        locale: z.string().nullable().optional(),
        reference_highlighting: z.boolean().prefault(true),
        code_lens: z.boolean().prefault(true),
      })
      .prefault({}),
    package_management: z
      .looseObject({
        manager: z.enum(PackageManagerNames).prefault("pip"),
      })
      .prefault({}),
    ai: z
      .looseObject({
        enabled: z.boolean().prefault(true),
        rules: z.string().prefault(""),
        max_tokens: z.number().int().positive().nullable().prefault(null),
        mode: z
          .enum(COPILOT_MODES)
          .transform((mode) => (mode === "manual" ? "ask" : mode))
          .prefault("ask"),
        inline_tooltip: z.boolean().prefault(false),
        allow_provider_config: z.boolean().prefault(true),
        open_ai: AiConfigSchema.optional(),
        github: AiConfigSchema.optional(),
        anthropic: AiConfigSchema.optional(),
        google: AiConfigSchema.optional(),
        ollama: AiConfigSchema.optional(),
        openrouter: AiConfigSchema.optional(),
        wandb: AiConfigSchema.optional(),
        opencode_go: AiConfigSchema.optional(),
        open_ai_compatible: AiConfigSchema.optional(),
        azure: AiConfigSchema.optional(),
        bedrock: z
          .looseObject({
            region_name: z.string().optional(),
            profile_name: z.string().optional(),
            aws_access_key_id: z.string().optional(),
            aws_secret_access_key: z.string().optional(),
          })
          .optional(),
        custom_providers: z.record(z.string(), AiConfigSchema).prefault({}),
        models: AiModelsSchema.prefault({
          displayed_models: [],
          custom_models: [],
        }),
      })
      .prefault({}),
    experimental: z
      .looseObject({
        markdown: z.boolean().optional(),
        isolate_apps: z.boolean().prefault(false),
        debugger: z.boolean().prefault(false),
        line_timing: z.boolean().prefault(false),
        execution_type: z.enum(["relaxed", "strict"]).prefault("relaxed"),
        // Add new experimental features here
      })
      // Pass through so that we don't remove any extra keys that the user has added.
      .prefault(() => ({})),
    server: z
      .looseObject({
        skip_update_check: z.boolean().optional(),
        session_cookie_secure: z.boolean().optional(),
        session_cookie_partitioned: z.boolean().optional(),
        session_secret: z.string().nullish().prefault(null),
        disable_file_downloads: z.boolean().prefault(false),
        transport: z.enum(["websocket", "sse"]).optional(),
      })
      .prefault(() => ({})),
    language_servers: z
      .looseObject({
        pylsp: z
          .looseObject({
            enabled: z.boolean().prefault(false),
            enable_mypy: z.boolean().prefault(true),
            enable_ruff: z.boolean().prefault(true),
            enable_flake8: z.boolean().prefault(false),
            enable_pydocstyle: z.boolean().prefault(false),
            enable_pylint: z.boolean().prefault(false),
            enable_pyflakes: z.boolean().prefault(false),
          })
          .prefault({}),
      })
      .prefault({}),
    snippets: z
      .looseObject({
        custom_paths: z.array(z.string()).prefault([]),
        include_default_snippets: z.boolean().prefault(true),
      })
      .prefault({}),
    diagnostics: z
      .looseObject({
        enabled: z.boolean().optional(),
        sql_linter: z.boolean().prefault(true),
      })
      .prefault(() => ({})),
    file_browser: z
      .looseObject({
        folders: z
          .array(
            z.object({
              path: z.string(),
              name: z.string().nullish().prefault(null),
            }),
          )
          .prefault([]),
      })
      .nullish()
      .prefault(null),
    sharing: z
      .looseObject({
        html: z.boolean().optional(),
        wasm: z.boolean().optional(),
        molab: z.boolean().optional(),
      })
      .nullish()
      .prefault(null),
    lint: z
      .looseObject({
        select: z.array(z.string()).prefault([]),
        ignore: z.array(z.string()).prefault([]),
      })
      .prefault({}),
    datasources: z
      .looseObject({
        auto_discover_schemas: z
          .union([z.boolean(), z.literal("auto")])
          .optional(),
        auto_discover_tables: z
          .union([z.boolean(), z.literal("auto")])
          .optional(),
        auto_discover_columns: z
          .union([z.boolean(), z.literal("auto")])
          .optional(),
      })
      .prefault({}),
    venv: z
      .looseObject({
        path: z.string().nullable().prefault(null),
        writable: z.boolean().prefault(false),
      })
      .prefault({}),
    cache: z
      .looseObject({
        verification: z.enum(["off", "on", "strict"]).prefault("off"),
        store: z.unknown().prefault(null),
        loader: z.string().prefault("lazy"),
      })
      .prefault({}),
    signing: z
      .looseObject({
        trusted_signers: z.record(z.string(), z.string()).prefault({}),
        private_key_path: z.string().nullable().prefault(null),
      })
      .prefault({}),
    mcp: z
      .looseObject({
        presets: z.array(z.enum(["marimo", "context7"])).prefault([]),
        mcpServers: z.record(z.string(), z.unknown()).prefault({}),
      })
      .optional()
      .prefault({}),
  })
  .partial()
  .prefault(() => ({
    completion: {},
    save: {},
    formatting: {},
    keymap: {},
    runtime: {},
    display: {},
    diagnostics: {},
    language_servers: {},
    snippets: {},
    file_browser: null,
    sharing: null,
    experimental: {},
    server: {},
    ai: {},
    package_management: {},
    mcp: {},
    cache: {},
    venv: {},
    signing: {},
    lint: {},
    datasources: {},
  }));
export type UserConfig = MarimoConfig;
export type SaveConfig = UserConfig["save"];
export type CompletionConfig = UserConfig["completion"];
export type KeymapConfig = UserConfig["keymap"];
export type LSPConfig = UserConfig["language_servers"];
export type DiagnosticsConfig = UserConfig["diagnostics"];
export type DisplayConfig = UserConfig["display"];
export type AiConfig = UserConfig["ai"];

export const AppTitleSchema = z.string();
export const SqlOutputSchema = z
  .enum(VALID_SQL_OUTPUT_FORMATS)
  .prefault("auto");

/**
 * The notebook's app config. The defaults are Python's `_AppConfig` defaults,
 * since the host document carries only what differs from them.
 */
export const AppConfigSchema = z
  .object({
    width: z
      .enum(VALID_APP_WIDTHS)
      .prefault("compact")
      .transform((width) => {
        if (width === "normal") {
          return "compact";
        }
        return width;
      }),
    app_title: AppTitleSchema.nullish(),
    css_file: z.string().nullish(),
    html_head_file: z.string().nullish(),
    auto_download: z.array(z.enum(AUTO_DOWNLOAD_FORMATS)).prefault([]),
    sql_output: SqlOutputSchema,
  })
  .prefault(() => ({
    width: "compact" as const,
    auto_download: [],
    sql_output: "auto" as const,
  }));
export type AppConfig = z.infer<typeof AppConfigSchema>;

export function parseAppConfig(config: unknown) {
  try {
    return AppConfigSchema.parse(config);
  } catch (error) {
    Logger.error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
    return AppConfigSchema.parse({});
  }
}

export function parseUserConfig(config: unknown): UserConfig {
  try {
    const parsed = UserConfigSchema.parse(config);
    for (const [key, value] of Object.entries(parsed.experimental ?? {})) {
      if (value === true) {
        Logger.log(`🧪 Experimental feature "${key}" is enabled.`);
      }
    }
    return parsed as unknown as UserConfig;
  } catch (error) {
    if (error instanceof z.ZodError) {
      Logger.error(
        `Marimo got an unexpected value in the configuration file: ${z.prettifyError(error)}`,
      );
    } else {
      Logger.error(
        `Marimo got an unexpected value in the configuration file: ${error}`,
      );
    }
    return defaultUserConfig();
  }
}

export function parseConfigOverrides(config: unknown): {} {
  try {
    const overrides = config as {};
    invariant(
      typeof overrides === "object",
      "internal-error: marimo-config-overrides is not an object",
    );
    if (Object.keys(overrides).length > 0) {
      Logger.log("🔧 Project configuration overrides:", overrides);
    }
    return overrides as {};
  } catch (error) {
    Logger.error(`Marimo got an unexpected configuration overrides: ${error}`);
    return {};
  }
}

export function defaultUserConfig(): UserConfig {
  const defaultConfig: Partial<Record<keyof UserConfig, unknown>> = {
    completion: {},
    save: {},
    formatting: {},
    keymap: {},
    runtime: {},
    display: {},
    diagnostics: {},
    language_servers: {},
    snippets: {},
    file_browser: null,
    sharing: null,
    experimental: {},
    server: {},
    ai: {},
    package_management: {},
    mcp: {},
    cache: {},
    venv: {},
    signing: {},
    lint: {},
    datasources: {},
  };
  return UserConfigSchema.parse(defaultConfig) as UserConfig;
}
