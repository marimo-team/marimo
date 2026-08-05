/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { cellId } from "@/__tests__/branded";
import { LogViewer } from "@/components/editor/chrome/panels/logs-panel";
import { Dialog } from "../components/ui/dialog";
import { TooltipProvider } from "../components/ui/tooltip";

const meta: Meta<typeof LogViewer> = {
  title: "LogViewer",
  component: LogViewer,
  args: {},
};

export default meta;
type Story = StoryObj<typeof LogViewer>;

export const Primary: Story = {
  render: () => (
    <Dialog>
      <TooltipProvider>
        <LogViewer
          logs={[
            {
              timestamp: Date.now(),
              level: "stdout",
              source: { type: "cell", cellId: cellId("cell1") },
              message: "Hello world!",
            },
            {
              timestamp: Date.now(),
              level: "stdout",
              source: { type: "cell", cellId: cellId("cell1") },
              message: "Running cell...",
            },
            {
              timestamp: Date.now(),
              level: "stdout",
              source: { type: "cell", cellId: cellId("cell1") },
              message: "Done!",
            },
            {
              timestamp: Date.now(),
              level: "stderr",
              source: { type: "cell", cellId: cellId("cell2") },
              message: "Output is too large!",
            },
            {
              timestamp: Date.now(),
              level: "stderr",
              source: { type: "cell", cellId: cellId("cell2") },
              message: "String length is too short.".repeat(100),
            },
            {
              timestamp: Date.now(),
              level: "stderr",
              source: { type: "lsp", name: "pylsp" },
              message: "Failed to load plugin 'ruff': not installed",
            },
            ...Array.from({ length: 100 }).map(() => ({
              timestamp: Date.now(),
              level: "stdout" as const,
              source: { type: "cell", cellId: cellId("cell1") } as const,
              message: "Running cell...",
            })),
          ]}
        />
      </TooltipProvider>
    </Dialog>
  ),
};

export const Empty: Story = {
  render: () => (
    <Dialog>
      <TooltipProvider>
        <LogViewer logs={[]} />
      </TooltipProvider>
    </Dialog>
  ),
};
