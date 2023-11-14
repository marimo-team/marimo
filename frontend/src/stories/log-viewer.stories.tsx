/* Copyright 2023 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react";
import { Dialog } from "../components/ui/dialog";
import { TooltipProvider } from "../components/ui/tooltip";
import { LogViewer } from "@/components/editor/chrome/panels/logs-panel";
import { CellId } from "@/core/cells/ids";

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
              level: "info",
              cellId: "cell1" as CellId,
              message: "Hello world!",
            },
            {
              timestamp: Date.now(),
              level: "info",
              cellId: "cell1" as CellId,
              message: "Running cell...",
            },
            {
              timestamp: Date.now(),
              level: "info",
              cellId: "cell1" as CellId,
              message: "Done!",
            },
            {
              timestamp: Date.now(),
              level: "warning",
              cellId: "cell2" as CellId,
              message: "Output is too large!",
            },
            {
              timestamp: Date.now(),
              level: "error",
              cellId: "cell2" as CellId,
              message: "String length is too short.".repeat(100),
            },
            ...Array.from({ length: 100 }).map((_, index) => ({
              timestamp: Date.now(),
              level: "info" as const,
              cellId: "cell1" as CellId,
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
