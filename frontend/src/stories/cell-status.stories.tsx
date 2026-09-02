/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react-vite";
import {
  CellStatusComponent,
  type CellStatusComponentProps,
} from "@/components/editor/cell/CellStatus";
import { TooltipProvider } from "@/components/ui/tooltip";
import { deriveCellSemanticState } from "@/core/cells/semantic-state";
import {
  createCell,
  createCellRuntimeState,
  type CellData,
  type CellRuntimeState,
} from "@/core/cells/types";
import { CellId } from "@/core/cells/ids";
import { Time, type Milliseconds } from "@/utils/time";

const cellId = CellId.create();
const state = (
  data: Partial<CellData> = {},
  runtime: Partial<CellRuntimeState> = {},
) =>
  deriveCellSemanticState(
    createCell({ id: cellId, ...data }),
    createCellRuntimeState(runtime),
  );

const meta: Meta<typeof CellStatusComponent> = {
  title: "CellStatusComponent",
  component: CellStatusComponent,
  args: { editing: true, state: state() },
};

export default meta;

const Template: StoryFn<CellStatusComponentProps> = (args) => (
  <TooltipProvider>
    <div className="bg-background p-4">
      <CellStatusComponent {...args} />
    </div>
  </TooltipProvider>
);

export const NotRun = Template.bind({});
NotRun.args = { state: state() };

export const Outdated = Template.bind({});
Outdated.args = {
  state: state(
    { edited: true, lastExecutionTime: 100 },
    { runElapsedTimeMs: 100 as Milliseconds },
  ),
};

export const Interrupted = Template.bind({});
Interrupted.args = {
  state: state({}, { interrupted: true, runElapsedTimeMs: 50 as Milliseconds }),
};

export const Stopped = Template.bind({});
Stopped.args = {
  state: state({}, { stopped: true }),
};

export const Failed = Template.bind({});
Failed.args = {
  state: state({}, { errored: true, runElapsedTimeMs: 50 as Milliseconds }),
};

export const Running = Template.bind({});
Running.args = {
  state: state(
    {},
    { status: "running", runStartTimestamp: Time.now().toSeconds() },
  ),
};

export const Queued = Template.bind({});
Queued.args = { state: state({}, { status: "queued" }) };

export const Paused = Template.bind({});
Paused.args = {
  state: state({ config: { disabled: true, hide_code: false, column: null } }),
};

export const Blocked = Template.bind({});
Blocked.args = { state: state({}, { status: "disabled-transitively" }) };

export const Successful = Template.bind({});
Successful.args = {
  state: state({}, { runElapsedTimeMs: 1500 as Milliseconds }),
};
