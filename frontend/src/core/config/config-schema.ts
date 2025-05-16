/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Logger } from "@/utils/Logger";
import {
  getMarimoAppConfig,
  getMarimoConfigOverrides,
  getMarimoUserConfig,
} from "../dom/marimo-tag";
import type { MarimoConfig } from "../network/types";
import { invariant } from "@/utils/invariant";

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

export const UserConfigSchema = z
  .object({
    completion: z
      .object({
        activate_on_typing: z.boolean().default(true),
        copilot: z
          .union([z.boolean(), z.enum(["github", "codeium", "custom"])])
          .default(false)
          .transform((copilot) => {
            if (copilot === true) {
              return "github";
            }
            return copilot;
          }),
        codeium_api_key: z.string().nullish(),
      })
      .passthrough()
      .default({}),
    save: z
      .object({
        autosave: z.enum(["off", "after_delay"]).default("after_delay"),
        autosave_delay: z
          .number()
          .nonnegative()
          // Ensure that the delay is at least 1 second
          .transform((millis) => Math.max(millis, 1000))
          .default(1000),
        format_on_save: z.boolean().default(false),
      })
      .passthrough()
      .default({}),
    formatting: z
      .object({
        line_length: z
          .number()
          .nonnegative()
          .default(79)
          .transform((n) => Math.min(n, 1000)),
      })
      .passthrough()
      .default({}),
    keymap: z
      .object({
        preset: z.enum(["default", "vim"]).default("default"),
        overrides: z.record(z.string()).default({}),
      })
      .passthrough()
      .default({}),
    runtime: z
      .object({
        auto_instantiate: z.boolean().default(true),
        on_cell_change: z.enum(["lazy", "autorun"]).default("autorun"),
        auto_reload: z.enum(["off", "lazy", "autorun"]).default("off"),
        watcher_on_save: z.enum(["lazy", "autorun"]).default("lazy"),
        default_sql_output: z.enum(VALID_SQL_OUTPUT_FORMATS).default("auto"),
      })
      .passthrough()
      .default({}),
    display: z
      .object({
        theme: z.enum(["light", "dark", "system"]).default("light"),
        code_editor_font_size: z.number().nonnegative().default(14),
        cell_output: z.enum(["above", "below"]).default("above"),
        dataframes: z.enum(["rich", "plain"]).default("rich"),
        default_table_page_size: z.number().default(10),
        default_width: z
          .enum(VALID_APP_WIDTHS)
          .default("medium")
          .transform((width) => {
            if (width === "normal") {
              return "compact";
            }
            return width;
          }),
      })
      .passthrough()
      .default({}),
    package_management: z
      .object({
        manager: z.enum(PackageManagerNames).default("pip"),
      })
      .passthrough()
      .default({ manager: "pip" }),
    ai: z
      .object({
        rules: z.string().default(""),
        open_ai: z
          .object({
            api_key: z.string().optional(),
            base_url: z.string().optional(),
            model: z.string().optional(),
          })
          .optional(),
        anthropic: z
          .object({
            api_key: z.string().optional(),
          })
          .optional(),
        google: z
          .object({
            api_key: z.string().optional(),
          })
          .optional(),
        bedrock: z
          .object({
            region_name: z.string().optional(),
            profile_name: z.string().optional(),
            aws_access_key_id: z.string().optional(),
            aws_secret_access_key: z.string().optional(),
          })
          .optional(),
      })
      .passthrough()
      .default({}),
    experimental: z
      .object({
        markdown: z.boolean().optional(),
        rtc: z.boolean().optional(),
        // Add new experimental features here
      })
      // Pass through so that we don't remove any extra keys that the user has added.
      .passthrough()
      .default({}),
    server: z.object({}).passthrough().default({}),
  })
  // Pass through so that we don't remove any extra keys that the user has added
  .passthrough()
  .default({
    completion: {},
    save: {},
    formatting: {},
    keymap: {},
    runtime: {},
    display: {},
    experimental: {},
    server: {},
    ai: {
      rules: "",
      open_ai: {},
    },
  });
export type UserConfig = MarimoConfig;
export type SaveConfig = UserConfig["save"];
export type CompletionConfig = UserConfig["completion"];
export type KeymapConfig = UserConfig["keymap"];
export type LSPConfig = UserConfig["language_servers"];
export type DiagnosticsConfig = UserConfig["diagnostics"];

export const AppTitleSchema = z.string();
export const SqlOutputSchema = z.enum(VALID_SQL_OUTPUT_FORMATS).default("auto");

export const AppConfigSchema = z
  .object({
    width: z
      .enum(VALID_APP_WIDTHS)
      .default("medium")
      .transform((width) => {
        if (width === "normal") {
          return "compact";
        }
        return width;
      }),
    app_title: AppTitleSchema.nullish(),
    css_file: z.string().nullish(),
    html_head_file: z.string().nullish(),
    auto_download: z.array(z.enum(["html", "markdown", "ipynb"])).default([]),
    sql_output: SqlOutputSchema,
  })
  .default({ width: "medium", auto_download: [] });
export type AppConfig = z.infer<typeof AppConfigSchema>;

export function parseAppConfig() {
  try {
    return AppConfigSchema.parse(getMarimoAppConfig());
  } catch (error) {
    Logger.error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
    return AppConfigSchema.parse({});
  }
}

export function parseUserConfig(): UserConfig {
  try {
    const parsed = UserConfigSchema.parse(getMarimoUserConfig());
    for (const [key, value] of Object.entries(parsed.experimental)) {
      if (value === true) {
        Logger.log(`🧪 Experimental feature "${key}" is enabled.`);
      }
    }
    return parsed as unknown as UserConfig;
  } catch (error) {
    Logger.error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
    return defaultUserConfig();
  }
}

export function parseConfigOverrides(): {} {
  try {
    const overrides = getMarimoConfigOverrides() as {};
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
  return UserConfigSchema.parse({}) as unknown as UserConfig;
}
