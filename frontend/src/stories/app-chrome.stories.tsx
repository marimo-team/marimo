/* Copyright 2023 Marimo. All rights reserved. */
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppChrome } from "@/editor/chrome/wrapper/app-chrome";
import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta<typeof AppChrome> = {
  title: "AppChrome",
  component: AppChrome,
  args: {},
};

export default meta;
type Story = StoryObj;

export const Primary: Story = {
  render: () => (
    <TooltipProvider>
      <div className="flex top-0 left-0 right-0 bottom-0 absolute">
        <AppChrome>
          <div className="p-5">marimo application</div>
        </AppChrome>
      </div>
    </TooltipProvider>
  ),
};
