/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { type RuntimeStory, runtimeStoryMeta } from "./runtime-story";

const meta = {
  ...runtimeStoryMeta,
  title: "Runtime/Sandbox maintenance",
  args: { ...runtimeStoryMeta.args, backend: "uv", surface: "packages" },
} satisfies Meta<typeof RuntimeStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Syncing: Story = {
  name: "Sync — in progress",
  args: { phase: "syncing" },
};
export const SyncFailed: Story = {
  name: "Sync — failed",
  args: { phase: "sync-failed" },
};
export const Synced: Story = {
  name: "Sync — completed",
  args: { phase: "synced" },
};
export const RestartRequired: Story = {
  name: "Sync — restart required",
  args: { phase: "restart-required" },
};
export const ManifestEditor: Story = {
  name: "Manifest — edit",
  args: { surface: "manifest", phase: "failed" },
};
export const ManifestSaveFailed: Story = {
  name: "Manifest — failed save",
  args: { surface: "manifest", phase: "failed", saveResult: "failure" },
};
export const ManifestChanged: Story = {
  name: "Manifest — changed on disk",
  args: { surface: "manifest", phase: "failed", saveResult: "stale" },
};
