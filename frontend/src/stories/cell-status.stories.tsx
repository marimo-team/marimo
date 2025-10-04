/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react-vite";
import {
  CellStatusComponent,
  type CellStatusComponentProps,
} from "@/components/editor/cell/CellStatus";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Seconds } from "@/utils/time";

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

export const Uninstantiated = Template.bind({});
Uninstantiated.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: true,
  elapsedTime: null,
};

export const StaleInputs = Template.bind({});
StaleInputs.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: true,
  uninstantiated: false,
  elapsedTime: 250,
};

export const IdleWithElapsedTime = Template.bind({});
IdleWithElapsedTime.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  elapsedTime: 1500,
};

export const IdleWithElapsedTimeAndLastRun = Template.bind({});
IdleWithElapsedTimeAndLastRun.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  elapsedTime: 1500,
  lastRunStartTimestamp: (Date.now() / 1000 - 300) as Seconds, // 5 minutes ago
};

export const CachedHit = Template.bind({});
CachedHit.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  cache: "hit",
  elapsedTime: null,
};

export const CachedAfterRunning = Template.bind({});
CachedAfterRunning.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  cache: "cached",
  elapsedTime: 2500,
};

export const RunningWithTimestamp = Template.bind({});
RunningWithTimestamp.args = {
  editing: true,
  status: "running",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  runStartTimestamp: (Date.now() / 1000 - 5) as Seconds, // started 5 seconds ago
  elapsedTime: null,
};

export const DisabledWithStaleInputs = Template.bind({});
DisabledWithStaleInputs.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: true,
  staleInputs: true,
  uninstantiated: false,
  elapsedTime: null,
};

export const EditedWithLongElapsedTime = Template.bind({});
EditedWithLongElapsedTime.args = {
  editing: true,
  status: "idle",
  edited: true,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  elapsedTime: 125000, // over 2 minutes
};

export const InterruptedWithLastRun = Template.bind({});
InterruptedWithLastRun.args = {
  editing: true,
  status: "idle",
  edited: false,
  interrupted: true,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  elapsedTime: 3000,
  lastRunStartTimestamp: (Date.now() / 1000 - 600) as Seconds, // 10 minutes ago
};

export const NotEditing = Template.bind({});
NotEditing.args = {
  editing: false,
  status: "idle",
  edited: false,
  interrupted: false,
  disabled: false,
  staleInputs: false,
  uninstantiated: false,
  elapsedTime: 100,
};
