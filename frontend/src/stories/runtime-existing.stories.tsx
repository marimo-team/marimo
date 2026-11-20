/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { type RuntimeStory, runtimeStoryMeta } from "./runtime-story";

const meta = {
  ...runtimeStoryMeta,
  title: "Runtime/Existing environment",
  args: { ...runtimeStoryMeta.args, backend: null, phase: "starting" },
} satisfies Meta<typeof RuntimeStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Walkthrough: Story = {
  name: "Walkthrough",
  args: { manual: true, detailsOpen: true },
};
export const NotebookConnecting: Story = {
  name: "Notebook — connecting",
  args: {},
};
export const NotebookFailed: Story = {
  name: "Notebook — failure and retry",
  args: { phase: "failed" },
};
export const EmptyNotebook: Story = {
  name: "Empty notebook — connecting",
  args: { existingCells: false },
};
export const DetailsConnecting: Story = {
  name: "Sidebar — connecting",
  args: { surface: "packages" },
};
export const DetailsFailed: Story = {
  name: "Sidebar — failure details",
  args: { surface: "packages", phase: "failed" },
};
export const Ready: Story = {
  name: "Sidebar — ready",
  args: { surface: "packages", phase: "ready" },
};
export const Completion: Story = {
  name: "Automatic completion",
  args: { interactive: true },
};
