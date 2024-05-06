/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Logger } from "@/utils/Logger";
import { getMarimoAppConfig, getMarimoUserConfig } from "../dom/marimo-tag";

// This has to be defined in the same file as the zod schema to satisfy zod
export const PackageManagerNames = [
  "pip",
  "uv",
  "rye",
  "poetry",
  "pixi",
] as const;
export type PackageManagerName = (typeof PackageManagerNames)[number];

export const UserConfigSchema = z
  .object({
    completion: z
      .object({
        activate_on_typing: z.boolean().default(true),
        copilot: z.boolean().default(false),
      })
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
      .default({}),
    formatting: z
      .object({
        line_length: z
          .number()
          .nonnegative()
          .default(79)
          .transform((n) => Math.min(n, 1000)),
      })
      .default({}),
    keymap: z
      .object({
        preset: z.enum(["default", "vim"]).default("default"),
      })
      .default({}),
    runtime: z
      .object({
        auto_instantiate: z.boolean().default(true),
        on_cell_change: z.enum(["lazy", "autorun"]).default("autorun"),
        auto_reload: z.enum(["off", "lazy", "autorun"]).default("off"),
      })
      .default({}),
    display: z
      .object({
        theme: z.enum(["light", "dark", "system"]).default("light"),
        code_editor_font_size: z.number().nonnegative().default(14),
        cell_output: z.enum(["above", "below"]).default("above"),
      })
      .default({}),
    package_management: z
      .object({
        manager: z.enum(PackageManagerNames).default("pip"),
      })
      .default({ manager: "pip" }),
    ai: z
      .object({
        open_ai: z
          .object({
            api_key: z.string().optional(),
            base_url: z.string().optional(),
            model: z.string().optional(),
          })
          .optional(),
      })
      .default({}),
    experimental: z
      .object({})
      // Pass through so that we don't remove any extra keys that the user has added.
      .passthrough()
      .default({}),
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
  });
export type UserConfig = z.infer<typeof UserConfigSchema>;
export type SaveConfig = UserConfig["save"];
export type CompletionConfig = UserConfig["completion"];
export type KeymapConfig = UserConfig["keymap"];

export const APP_WIDTHS = ["normal", "medium", "full"] as const;
export const AppTitleSchema = z
  .string()
  .regex(new RegExp("^[A-Za-z0-9-_' ]*$"), {
    message: "Invalid application title",
  });
export const AppConfigSchema = z
  .object({
    width: z.enum(APP_WIDTHS).default("normal"),
    app_title: AppTitleSchema.nullish(),
  })
  .default({ width: "normal" });
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
    return parsed;
  } catch (error) {
    Logger.error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
    return defaultUserConfig();
  }
}

export function defaultUserConfig(): UserConfig {
  return UserConfigSchema.parse({});
}
