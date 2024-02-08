/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { Logger } from "@/utils/Logger";
import {
  getRawMarimoAppConfig,
  getRawMarimoUserConfig,
} from "../dom/marimo-tag";

export const UserConfigSchema = z
  .object({
    completion: z.object({
      activate_on_typing: z.boolean(),
      copilot: z.boolean(),
    }),
    save: z.object({
      autosave: z.enum(["off", "after_delay"]).default("after_delay"),
      autosave_delay: z
        .number()
        .nonnegative()
        // Ensure that the delay is at least 1 second
        .transform((millis) => Math.max(millis, 1000))
        .default(1000),
      format_on_save: z.boolean().default(false),
    }),
    formatting: z
      .object({
        line_length: z
          .number()
          .nonnegative()
          .default(79)
          .transform((n) => Math.min(n, 1000)),
      })
      .default({ line_length: 79 }),
    keymap: z.object({
      preset: z.enum(["default", "vim"]).default("default"),
    }),
    runtime: z
      .object({
        auto_instantiate: z.boolean(),
      })
      .default({ auto_instantiate: true }),
    display: z
      .object({
        theme: z.enum(["light", "dark", "system"]).default("light"),
        code_editor_font_size: z.number().nonnegative().default(14),
        cell_output: z.enum(["above", "below"]).default("above"),
      })
      .default({
        theme: "light",
        code_editor_font_size: 14,
        cell_output: "above",
      }),
    experimental: z
      .object({
        layouts: z.boolean().optional(),
      })
      // Pass through so that we don't remove any extra keys that the user has added.
      .passthrough()
      .default({}),
  })
  // Pass through so that we don't remove any extra keys that the user has added.
  .passthrough();
export type UserConfig = z.infer<typeof UserConfigSchema>;
export type SaveConfig = UserConfig["save"];
export type CompletionConfig = UserConfig["completion"];
export type KeymapConfig = UserConfig["keymap"];

export const AppConfigSchema = z.object({
  width: z.enum(["full", "normal"]).default("normal"),
});
export type AppConfig = z.infer<typeof AppConfigSchema>;

export function parseAppConfig() {
  try {
    return AppConfigSchema.parse(JSON.parse(getRawMarimoAppConfig()));
  } catch (error) {
    throw new Error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
  }
}

export function parseUserConfig() {
  try {
    const parsed = UserConfigSchema.parse(JSON.parse(getRawMarimoUserConfig()));
    for (const [key, value] of Object.entries(parsed.experimental)) {
      if (value === true) {
        Logger.log(`🧪 Experimental feature "${key}" is enabled.`);
      }
    }
    return parsed;
  } catch (error) {
    throw new Error(
      `Marimo got an unexpected value in the configuration file: ${error}`,
    );
  }
}
