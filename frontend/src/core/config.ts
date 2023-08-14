/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { assertExists } from "../utils/assertExists";

const SaveConfigSchema = z.object({
  autosave: z.enum(["off", "after_delay"]),
  autosave_delay: z.number().nonnegative(),
});

const CompletionConfigSchema = z.object({
  activate_on_typing: z.boolean(),
});

export const UserConfigSchema = z.object({
  completion: CompletionConfigSchema,
  save: SaveConfigSchema,
});
export type UserConfig = z.infer<typeof UserConfigSchema>;
export type SaveConfig = z.infer<typeof SaveConfigSchema>;
export type CompletionConfig = z.infer<typeof CompletionConfigSchema>;

export function getAppConfig() {
  const tag = document.querySelector<HTMLElement>("marimo-config");
  assertExists(tag, "internal-error: marimo-config tag not found");

  const configData = tag.dataset.config;
  assertExists(configData, "internal-error: missing config");

  try {
    return UserConfigSchema.parse(JSON.parse(configData));
  } catch (error) {
    throw new Error(
      `Marimo got an unexpected value in the configuration file: ${error}`
    );
  }
}
