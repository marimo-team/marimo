/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { type RuntimeStory, runtimeStoryMeta } from "./runtime-story";

const meta = {
  ...runtimeStoryMeta,
  title: "Runtime/uv sandbox",
  args: { ...runtimeStoryMeta.args, backend: "uv" },
} satisfies Meta<typeof RuntimeStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Walkthrough: Story = {
  name: "Walkthrough",
  args: { manual: true, detailsOpen: true },
};
export const NotebookPreparing: Story = {
  name: "Notebook — preparing environment",
  args: {},
};
export const NotebookStarting: Story = {
  name: "Notebook — starting kernel",
  args: { phase: "starting" },
};
export const NotebookFailed: Story = {
  name: "Notebook — setup failed",
  args: { phase: "failed" },
};
export const EmptyNotebook: Story = {
  name: "Empty notebook — preparing",
  args: { existingCells: false },
};
export const EmptyNotebookFailed: Story = {
  name: "Empty notebook — setup failed",
  args: { existingCells: false, phase: "failed" },
};
export const DetailsPreparing: Story = {
  name: "Sidebar — preparing environment",
  args: { surface: "packages" },
};
export const DetailsStarting: Story = {
  name: "Sidebar — starting kernel",
  args: { surface: "packages", phase: "starting" },
};
export const DetailsFailed: Story = {
  name: "Sidebar — setup failed",
  args: { surface: "packages", phase: "failed" },
};
export const Ready: Story = {
  name: "Sidebar — ready",
  args: { surface: "packages", phase: "ready" },
};
export const LiveOutput: Story = {
  name: "Sidebar — live output",
  args: { surface: "packages", interactive: true },
};
