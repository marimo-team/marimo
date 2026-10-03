/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  ProgressStages,
  type ProgressState,
} from "@/components/ui/progress-stages";

function ProgressStagesStory({
  state,
  completedStage,
}: {
  state: ProgressState;
  completedStage: boolean;
}) {
  return (
    <div className="w-80 space-y-6">
      <p className="text-sm text-muted-foreground">
        Isolated stage styling. For the actual notebook and sidebar, use the
        walkthroughs under Runtime.
      </p>
      <ProgressStages
        label="Example stages"
        stages={[
          ...(completedStage
            ? [
                {
                  id: "previous",
                  state: "succeeded" as const,
                  title: "Previous stage",
                  description: "This stage has finished.",
                },
              ]
            : []),
          {
            id: "current",
            state,
            title: "Current stage",
            description: "Change the state using the Storybook controls.",
          },
        ]}
      />
    </div>
  );
}

const meta = {
  title: "UI Primitives/ProgressStages",
  component: ProgressStagesStory,
  parameters: { layout: "centered" },
  args: { state: "running", completedStage: true },
  argTypes: {
    state: {
      control: "radio",
      options: ["waiting", "running", "succeeded", "failed"],
    },
  },
} satisfies Meta<typeof ProgressStagesStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const MultipleStages: Story = {};
export const SingleStage: Story = { args: { completedStage: false } };
