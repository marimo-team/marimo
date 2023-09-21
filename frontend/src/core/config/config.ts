/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { assertExists } from "../../utils/assertExists";

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
    }),
    keymap: z.object({
      preset: z.enum(["default", "vim"]).default("default"),
    }),
    experimental: z
      .object({
        theming: z.boolean().optional(),
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
    return AppConfigSchema.parse(JSON.parse(getConfig("app")));
  } catch (error) {
    throw new Error(
      `Marimo got an unexpected value in the configuration file: ${error}`
    );
  }
}

export function parseUserConfig() {
  try {
    return UserConfigSchema.parse(JSON.parse(getConfig("user")));
  } catch (error) {
    throw new Error(
      `Marimo got an unexpected value in the configuration file: ${error}`
    );
  }
}

function getConfig(kind: "user" | "app") {
  const tagName = kind === "user" ? "marimo-user-config" : "marimo-app-config";
  const tag = document.querySelector<HTMLElement>(tagName);
  assertExists(tag, `internal-error: ${tagName} tag not found`);

  const configData = tag.dataset.config;
  assertExists(configData, "internal-error: missing config");

  return configData;
}
