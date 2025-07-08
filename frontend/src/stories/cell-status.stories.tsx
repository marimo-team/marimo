/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react-vite";
import {
  CellStatusComponent,
  type CellStatusComponentProps,
} from "@/components/editor/cell/CellStatus";
import { TooltipProvider } from "@/components/ui/tooltip";

const meta: Meta<typeof CellStatusComponent> = {
  title: "CellStatusComponent",
  component: CellStatusComponent,
  args: {},
};

export default meta;

const Template: StoryFn<CellStatusComponentProps> = (args) => (
  <TooltipProvider>
    <div className="bg-background">
      <CellStatusComponent {...args} />
    </div>
  </TooltipProvider>
);

export const Idle = Template.bind({});
Idle.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const Edited = Template.bind({});
Edited.args = {
  editing: true,
  status: "idle",
  edited: true,
  interrupted: false,
  disabled: false,
  elapsedTime: 100,
};

export const Interrupted = Template.bind({});
Interrupted.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: true,
  disabled: false,
  elapsedTime: 50,
};

export const Running = Template.bind({});
Running.args = {
  editing: true,
  status: "running",
  edited: false,
  interrupted: true,
  disabled: false,
  elapsedTime: 50,
};

export const Queued = Template.bind({});
Queued.args = {
  editing: true,
  status: "queued",
  edited: false,
  interrupted: true,
  disabled: false,
  elapsedTime: 50,
};

export const Disabled = Template.bind({});
Disabled.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const DisabledTransitively = Template.bind({});
DisabledTransitively.args = {
  editing: true,
  status: "disabled-transitively",
  edited: false,
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const DisabledTransitivelyAndEdited = Template.bind({});
DisabledTransitivelyAndEdited.args = {
  editing: true,
  status: "disabled-transitively",
  edited: true,
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const Stale = Template.bind({});
Stale.args = {
  editing: true,
  status: "disabled-transitively",
  staleInputs: true,
  edited: false,
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const StaleAndDisabled = Template.bind({});
StaleAndDisabled.args = {
  editing: true,
  status: "disabled-transitively",
  staleInputs: true,
  edited: false,
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const EditedStaleAndDisabled = Template.bind({});
EditedStaleAndDisabled.args = {
  editing: true,
  status: "disabled-transitively",
  staleInputs: true,
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const EditedAndStale = Template.bind({});
EditedAndStale.args = {
  editing: true,
  status: "disabled-transitively",
  edited: true,
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};
