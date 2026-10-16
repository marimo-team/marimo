/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { type RuntimeStory, runtimeStoryMeta } from "./runtime-story";

const meta = {
  ...runtimeStoryMeta,
  title: "Runtime/pixi sandbox",
  args: { ...runtimeStoryMeta.args, backend: "pixi" },
} satisfies Meta<typeof RuntimeStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Walkthrough: Story = {
  name: "Walkthrough",
  args: { manual: true, detailsOpen: true },
};
export const Ready: Story = {
  name: "Sidebar — ready",
  args: { surface: "packages", phase: "ready" },
};
export const Completion: Story = {
  name: "Notebook — automatic completion",
  args: { interactive: true },
};
export const EmptyCompletion: Story = {
  name: "Empty notebook — automatic completion",
  args: { interactive: true, existingCells: false },
};
