/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react-vite";
import {
  CellStatusComponent,
  type CellStatusComponentProps,
} from "@/components/editor/cell/CellStatus";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Milliseconds } from "@/utils/time";

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
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const Edited = Template.bind({});
Edited.args = {
  editing: true,
  status: "idle",
  freshness: { sourceChanged: true, inputsChanged: false },
  interrupted: false,
  disabled: false,
  elapsedTime: 100 as Milliseconds,
};

export const Interrupted = Template.bind({});
Interrupted.args = {
  editing: true,
  status: "idle",
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: true,
  disabled: false,
  elapsedTime: 50 as Milliseconds,
};

export const Running = Template.bind({});
Running.args = {
  editing: true,
  status: "running",
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: true,
  disabled: false,
  elapsedTime: 50 as Milliseconds,
};

export const Queued = Template.bind({});
Queued.args = {
  editing: true,
  status: "queued",
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: true,
  disabled: false,
  elapsedTime: 50 as Milliseconds,
};

export const Disabled = Template.bind({});
Disabled.args = {
  editing: true,
  status: "idle",
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const DisabledTransitively = Template.bind({});
DisabledTransitively.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: false, inputsChanged: false },
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const DisabledTransitivelyAndEdited = Template.bind({});
DisabledTransitivelyAndEdited.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: true, inputsChanged: false },
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const Stale = Template.bind({});
Stale.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: false, inputsChanged: true },
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};

export const StaleAndDisabled = Template.bind({});
StaleAndDisabled.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: false, inputsChanged: true },
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const EditedStaleAndDisabled = Template.bind({});
EditedStaleAndDisabled.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: false, inputsChanged: true },
  interrupted: false,
  disabled: true,
  elapsedTime: null,
};

export const EditedAndStale = Template.bind({});
EditedAndStale.args = {
  editing: true,
  status: "idle",
  blocked: true,
  freshness: { sourceChanged: true, inputsChanged: false },
  interrupted: false,
  disabled: false,
  elapsedTime: null,
};
